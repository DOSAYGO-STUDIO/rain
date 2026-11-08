nis1 - existing variant that passes all tests, and adds a counter to confound invertibility.

nis2 - new proposal to fold the state in half using the finalization step at every round ingest, and reset the high words (512 bits) to their initial values (or some approximation). worth testing this. in otherwords, nis2 has a full compression step at each ingest, after the round function. in other words, rainstorm-0 (OG rainstorm) has a mixing function at every ingest, and compression at the end. nis1 attempts to add some pseudo non invertibility through the use of a chained counter which is thrown away, but may still be invertible. nis2 proposes to compress at every ingest. this should solidify the design and balance mixing with non invertibility. nis2 is probably just as secure as nis1 (a fraction more so) but likely far faster.




