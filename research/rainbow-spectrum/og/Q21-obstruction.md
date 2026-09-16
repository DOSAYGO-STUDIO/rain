# Q21 — the advantage/leakage obstruction, what it actually forbids, and the door it leaves open

## The counting argument

Fix a construction: secret `theta` from a family of `2^s`, public `F_theta`, a
collision relation, digest length `n`. Write

    a = log2 C_generic - log2 C_private     the advantage the secret buys
    l = bits about theta revealed per published witness

**The exact definition.** Under a uniform key prior, leakage is by definition

    l(W) = log2 |Theta| - log2 |{ theta : V_theta(W) = 1 }|

and nothing more. **The random-family counting BASELINE** adds an assumption:
if the keyed verification relation is balanced/random-like, a wrong `theta'`
reproduces an `n`-bit coincidence with probability `2^-n`, giving
`#consistent ~ max(1, 2^(s-n))` and `l ~ min(s, n)`.

That baseline is NOT a theorem about every keyed family, and the exception is
exactly the phenomenon this program has been studying: a family whose members
share structured collisions accepts one witness under many keys, so `l` can be
far below `min(s, n)`. Treat `l ~ min(s,n)` as the generic expectation to beat,
not as a bound.

**The conditional half, which is the real obstruction.** If the private route is
cheap because it birthdays on a secret-dependent statistic `sigma_theta`, then
to leak less the keyholder must emit rarer witnesses -- ones compatible with more
of the family. Suppressing `l'` bits restricts the witness set to a `2^-l'`
fraction, and a birthday over a `2^-l'` fraction costs `2^(l'/2)` more:

    log2 C_private(l) = log2 C_private(l_max) + (l_max - l)/2
    a(l)              = a_max - (l_max - l)/2

so **`a <= l/2`** whenever `a_max <= l_max/2`, and advantage falls at half the
rate leakage does. This holds under an explicit model -- **a secret-dependent rare
subset searched by birthday** -- and is claimed only there. Narrower, but harder
to attack. Q14 measured this coordinate exactly: `l = (w-1) - v2(dC)`,
`log2 C ~ (w+r)/2`, generic `2^w`, hence `a = (w-r)/2 = l/2` -- on the line with
equality, and its own summary already said so in words.

## Measured (`og/run_leakage_advantage.py`)

Leakage by exhaustive posterior counting: enumerate ALL odd values of a secret
multiplier, count how many still make the published witness a collision.

    faithful B, k=2          consistent / family      l        a = 0.200w
    w=8   thetas[0] m0..m3       1-2 / 128          6-7 bits     1.6 bits
    w=10  thetas[0] m0..m3         1 / 512            9 bits     2.0 bits
    w=12  thetas[0] m0..m3         1 / 2048          11 bits     2.4 bits
    w=any thetas[1] m0..m3     ALL / all              0 bits        --

**One witness destroys faithful B.** A single published collision pins every one
of `thetas[0]`'s four multipliers UNIQUELY -- `l = 4(w-1)` bits against a secret
of `4(w-1)` bits. Survival is one witness.

**Half of B's key is gauge.** `thetas[1]` leaks nothing because it cannot: both
sides traverse the same merge mixer, which is a bijection, so the relation is
equivalent to equality BEFORE it and the last theta's multipliers cancel out of
the relation entirely (verified exactly). B's nominal key is twice its effective
key. Same phenomenon as Q19's `m1`/`m3` gauges, in a different place: parameters
that add key size without entering the relation.

Three data points, all consistent with `a <= l/2`:

    Q14 secret m3        a = l/2         ON the line
    faithful B           a = l/18        9x slack -- B is simply very leaky
    Q17 hidden coords    l ~ 0, a <= 0   at the origin

## The general claim is FALSE, and that is the useful part

Collision trapdoors exist. **Chameleon hash functions** (Krawczyk-Rabin) are
exactly this object: a public hash that is collision-resistant, plus a trapdoor
that makes collisions easy. So no argument can forbid the goal in general, and
any "proof" here is a proof about a restricted class.

What the class is, is precisely our situation. Classical chameleon hashes have a
known **key-exposure problem**: one collision reveals the trapdoor -- which is
exactly the faithful-B measurement above, arrived at independently. And the
known fix is not a better global structure, it is a change of shape:
**key-exposure-free chameleon hashing** binds each collision to a per-message
label, so a collision at label L says nothing about collisions at label L'.

That reframes every failure in this program:

    the advantage came from a GLOBAL structural weakness -- the pair-sum geometry,
    the DDT rays, a secret partition -- and a global weakness is exposed by every
    witness, because every witness is evidence about the same object.

`a <= l/2` is a theorem about global-structure trapdoors. It does not bind a
construction where the secret enters per-instance.

## The door -- superseded by Q22

The criterion first written here (does `S_L` shrink across labels) is WRONG, and
Q22 replaces it. Kept for the record: master-key entropy loss is not label
failure, because a perfect label that selects an independent subkey also shrinks
the global posterior. The operative question is capability transfer. See
`og/Q22-label-isolation.md`.

## The door, as originally (mis)stated

A construction escapes iff its private cheapness does NOT come from birthdaying
on a single secret-dependent statistic shared across witnesses. Concretely, the
target to build and attack:

  1. a per-witness label `L` (nonce, message prefix, or the chosen prefix itself);
  2. a private route whose cost is `2^(w/2)`-ish AT EVERY label;
  3. leakage measured the way this file measures it, but ACROSS labels: enumerate
     the secret coordinate, count candidates consistent with a witness at `L`,
     and check that the count does not shrink when a witness at `L'` is added.

Criterion 3 is the whole game and is directly measurable with the apparatus
already here. If the consistent set shrinks multiplicatively across labels, the
label is decorative and `a <= l/2` reasserts itself. If it does not, we have the
first construction in this program that is not paying the bill.

Rainbow's own structure suggests where the label lives: the seed. `mixB` takes
the seed as `b ^= a + iv`, so the seed already acts as a per-instance modifier of
the mixing, and the same-seed collision attack is explicitly *same-seed*. Whether
cross-seed witnesses intersect is a question about the existing function and can
be measured before anything is designed.

## Status

The counting argument is a sketch with a birthday assumption, exact in Q14's
coordinate. The leakage numbers are exhaustive, not estimated. The chameleon-hash
framing is the standard literature and should be read properly before the next
construction; the specific escape route (labels) is a design pattern, not a
result of this work.
