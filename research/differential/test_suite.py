"""Checks for statistical budgeting and search plumbing, including planted failures."""
import argparse
import math
import unittest
import suite
import smt_fold
import toy_multiply_differential as toy_multiply
import toy_product_differential as toy_product
import rainstorm_model
import two_round_staged
import smt_rebound
import smt_flat_collision
import verify_rebound_witness
from scan_production import ProductionNative

class ConstantHash:
    def hashes(self, algo, bits, seed, data, length, count):
        return bytes((bits//8)*count)

class Tests(unittest.TestCase):
    def test_fold_model_matches_native_original(self):
        native = suite.Native()
        for fill in (0, 1, 0x80, 0xff):
            message = bytes([fill]) * 64
            _, folded = smt_fold.state_before_and_after_fold(message, "OG")
            digest = native.hashes(1, 64, 0, message, 64, 1)
            self.assertEqual(folded[0], int.from_bytes(digest, "little"))

    def test_fold_cancellation_condition(self):
        before, after = smt_fold.state_before_and_after_fold(bytes(64), "A")
        for i in range(8):
            self.assertEqual(after[i], (before[i] - before[8 + i]) & suite.MASK)

    def test_toy_multiply_additive_difference_is_deterministic(self):
        counts = toy_multiply.additive_histogram(bits=8, shift=2, input_add=1)
        self.assertEqual(counts, {5: 256})

    def test_toy_multiply_xor_difference_exposes_operand_dependence(self):
        actual = toy_multiply.multiplication_histogram(bits=8, shift=2, input_xor=1)
        independent = toy_multiply.independent_add_histogram(bits=8, shift=2, input_xor=1)
        self.assertEqual(actual, {5: 128, 13: 64, 29: 32, 61: 16, 125: 8, 253: 8})
        self.assertEqual(independent[5] / (1 << 16), 0.25)
        self.assertEqual(actual[5] / (1 << 8), 0.5)

    def test_full_product_q_flip_has_zero_operand_collisions(self):
        result = toy_product.analyze(
            operand_bits=3, delta_p=0, delta_q=1,
            product_mode="full", mode="exhaustive", pairwise=True)
        observed = result["observed"]
        self.assertEqual(result["samples"], 64)
        self.assertEqual(observed["zero_difference_count"], 8)
        self.assertEqual(observed["zero_difference_probability"], 1 / 8)

    def test_product_rejects_unchanged_pair(self):
        with self.assertRaisesRegex(ValueError, "nonzero"):
            toy_product.analyze(operand_bits=4, delta_p=0, delta_q=0)

    def test_low_product_additive_difference_exposes_exact_identity(self):
        result = toy_product.analyze(
            operand_bits=4, delta_p=0, delta_q=1, product_mode="low",
            input_relation="add", output_relation="subtract",
            mode="exhaustive", pairwise=True)
        self.assertTrue(result["algebraic_check"]["verified_for_all_inputs"])
        self.assertEqual(result["observed"]["distinct_output_differences"], 16)
        self.assertEqual(result["observed"]["max_absolute_bit_bias"], 0)
        self.assertEqual(result["observed"]["zero_difference_probability"], 1 / 16)

    def test_low_product_supports_subtraction_as_negative_addition(self):
        result = toy_product.analyze(
            operand_bits=4, delta_p=0, delta_q=-1, product_mode="low",
            input_relation="add", output_relation="subtract",
            mode="exhaustive", pairwise=False)
        self.assertTrue(result["algebraic_check"]["verified_for_all_inputs"])
        self.assertEqual(result["pair_definition"]["delta_q_word"], "0xf")

    def test_production_model_matches_native(self):
        native = ProductionNative()
        for bits in (64, 256, 512):
            for length in (0, 8, 63, 64, 65):
                message = bytes((i * 37 + length) & 255 for i in range(length))
                modeled = rainstorm_model.hash_message(message, bits).digest
                actual = native.hashes(1, bits, 0, message, length, 1)
                self.assertEqual(modeled, actual, (bits, length))

    def test_left_low_map_is_bijective_and_ignores_high_half(self):
        data = [i * 0x0102030405060708 & rainstorm_model.MASK for i in range(8)]
        low = [i * 0x1111111111111111 & rainstorm_model.MASK for i in range(8)]
        state_a = low + [i for i in range(8)]
        state_b = low + [rainstorm_model.MASK - i for i in range(8)]
        out_a = rainstorm_model.weakfunc(state_a, data, True)
        out_b = rainstorm_model.weakfunc(state_b, data, True)
        self.assertEqual(out_a[:8], out_b[:8])
        self.assertEqual(rainstorm_model.invert_left_low(out_a[:8], data), low)

    def test_round_data_programming_hits_chosen_active_outputs(self):
        state = [(i * 0x102030405060708 + 17) & rainstorm_model.MASK
                 for i in range(16)]
        chosen = [(i * 0x1122334455667788 + 23) & rainstorm_model.MASK
                  for i in range(8)]
        for left in (False, True):
            data = rainstorm_model.program_round_data(state, chosen, left)
            output = rainstorm_model.weakfunc(state, data, left)
            active = output[:8] if left else output[8:]
            self.assertEqual(active, chosen)

    def test_programmed_late_lane_family_has_six_word_two_round_fold_prefix(self):
        initial = rainstorm_model.initial_state(64)
        observed = []
        for parameter in (0, 1, 0x0123456789abcdef, rainstorm_model.MASK):
            chosen = [0] * 6 + [parameter, (-parameter) & rainstorm_model.MASK]
            data = rainstorm_model.program_round_data(initial, chosen, False)
            state = rainstorm_model.weakfunc(initial, data, False)
            state = rainstorm_model.weakfunc(state, data, True)
            fold = [(state[i] - state[8 + i]) & rainstorm_model.MASK
                    for i in range(8)]
            self.assertEqual(fold[1:6], [0] * 5)
            observed.append(fold[0])
        self.assertGreater(len(set(observed)), 1)

    def test_known_g_collision_retains_words_one_to_five_after_one_padding_round(self):
        message_a = bytes.fromhex(
            "96ffffffffffffff58b56a3e941b7459bab074c685cf1afac"
            "02a2056945049fbfad0d3accbbf31fa1c4d50f00cd517fd"
            "193863ec0929f2a58af12b6ca5571671")
        message_b = bytes.fromhex(
            "96ffffffffffffff58b56a3e941b7459bab074c685cf1afac"
            "02a2056945049fbfad0d3accbbf31fa1c4d50f00cd517fd"
            "75d7ff14f926a35834c0702bc01e3bc8")
        result = verify_rebound_witness.replay(message_a, message_b)
        extended = result["one_real_padding_round_extension"]
        self.assertTrue(extended["fold_words_1_through_5_equal"])
        self.assertFalse(extended["fold_word_0_equal"])

    def test_weak_round_inverse_round_trip(self):
        state = [(i * 0x9e3779b97f4a7c15 + 0x123456789abcdef) &
                 rainstorm_model.MASK for i in range(16)]
        data = [(i * 0x0102030405060708 + 0xfedcba9876543210) &
                rainstorm_model.MASK for i in range(8)]
        for left in (False, True):
            output = rainstorm_model.weakfunc(state, data, left)
            self.assertEqual(
                rainstorm_model.invert_weakfunc(output, data, left), state)

    def test_symbolic_weak_round_inverse_matches_integer_inverse(self):
        import z3
        state = [(i * 0x123456789abcdef + 91) & rainstorm_model.MASK
                 for i in range(16)]
        data = [(i * 0xfedcba987654321 + 37) & rainstorm_model.MASK
                for i in range(8)]
        for left in (False, True):
            output = rainstorm_model.weakfunc(state, data, left)
            recovered = smt_rebound.symbolic_invert_weakfunc(
                [z3.BitVecVal(value, 64) for value in output],
                [z3.BitVecVal(value, 64) for value in data], left)
            self.assertEqual(
                [z3.simplify(value).as_long() for value in recovered], state)

    def test_flat_round_matches_integer_model(self):
        import z3
        state = [(0x1020304050607080 + i * 0x111111111111111) &
                 rainstorm_model.MASK for i in range(16)]
        data = [(0xfedcba9876543210 ^ (i * 0x0101010101010101)) &
                rainstorm_model.MASK for i in range(8)]
        for left in (False, True):
            expected = rainstorm_model.weakfunc(state, data, left)
            outputs = expected[:8] if left else expected[8:]
            actual, constraints = smt_flat_collision.symbolic_round_from_outputs(
                [z3.BitVecVal(value, 64) for value in state],
                [z3.BitVecVal(value, 64) for value in data], left,
                [z3.BitVecVal(value, 64) for value in outputs])
            solver = z3.Solver()
            solver.add(*constraints)
            self.assertEqual(solver.check(), z3.sat)
            self.assertEqual(
                [z3.simplify(value).as_long() for value in actual], expected)

    def test_rotated_xor_add_carry_solver_recovers_planted_words(self):
        for value, addend, constant in (
                (0, 1, 3),
                (rainstorm_model.MASK, 0x1234, 0x5678),
                (0x0123456789abcdef, 0xfedcba9876543210,
                 rainstorm_model.K[7])):
            difference = (
                ((value + addend) & rainstorm_model.MASK) ^
                ((rainstorm_model.rotl(value, 53) + constant) &
                 rainstorm_model.MASK)
            )
            solutions = two_round_staged.solve_rotated_xor_add(
                addend, constant, difference, 53)
            self.assertIn(value, solutions)

    def test_discovery_budget(self):
        for p in (.5,.01,1e-6):
            b=suite.bounds(1000,123,256,.01,p)
            n=b['samples_per_delta_for_discovery']
            self.assertLessEqual(math.log(123/p)+n*math.log1p(-p),math.log(.01))
            self.assertGreater(math.log(123/p)+(n-1)*math.log1p(-p),math.log(.01))

    def test_zero_event_bound(self):
        b=suite.bounds(100,7,64,.01,.1)
        self.assertAlmostEqual((1-b['zero_collision_upper'])**100,.01/7)

    def test_planted_collision_and_bias(self):
        args=argparse.Namespace(lengths=[1],all_bits=False,masks=None,algorithm='rainbow',bits=64,
            alpha=.01,samples=512,replay_seed=1,batch=127,hash_seed=0,p_min=.1)
        result=suite.scan(ConstantHash(),args)
        for row in result['records']:
            self.assertEqual(row['collisions'],512)
            self.assertEqual(row['most_frequent_count'],512)
            self.assertEqual(row['max_bit_bias'],.5)
            self.assertTrue(row['projection_alerts'])
            a,b=row['collision_witness']
            self.assertNotEqual(a,b)
            self.assertEqual(int(a,16)^int(b,16),int(row['input_xor_hex_little_endian'],16))

    def test_exhaustive_planted_collision(self):
        args=argparse.Namespace(domain_bits=4,algorithm='rainstorm',bits=128,hash_seed=0)
        result=suite.exhaustive(ConstantHash(),args)
        self.assertEqual(len(result['rows']),15)
        self.assertTrue(all(r['collision_count']==16 and r['max_probability']==1 for r in result['rows']))

if __name__=='__main__': unittest.main()
