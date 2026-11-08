# Guide to Dieharder Results

Test suite: dieharder version 3.31.2 Copyright 2003 Robert G. Brown

More information on dieharder test suite can be seen here: https://webhome.phy.duke.edu/~rgb/General/dieharder.php

Notes are provided below on how the various files were generated:

## Files

A discussion of how files were created and a summary of results therein are provided below. 

- `rainstorm-256.txt`: The source file was generated with `rainsum -a storm -s 256 -l 4000000 -o storm-256-4M.bin` which produces 4 million 256-bit output values. These are then read by dieharder as a stream of bits and shaped into whatever input format (ints, 32-bit ints, whatever) that a test requires. The file is "rewound" when it is exhausted. The total files size is 1 gigabyte. Dieharder was then run on the file with `dieharder -a -g 201 bow-256-4M.bin` to produce the included results file `rainbow-256.txt`. You can see that while most tests pass, some are weak and some fail. I think this is because the file is "too short" for some tests and is rewound. The reason I think this is because when I run it in "open format" (that is, streamed infinitely from rainsum and piped directly to dieharder, rather than through a fixed length file) all occasions for regret disappear. 
 
- `rainbow-256.txt`: The source file was generated with `rainsum -a bow -s 256 -l 4000000 -o bow-256-4M.bin` which produces 4 million 256-bit output values. These are then read by dieharder as a stream of bits and shaped into whatever input format (ints, 32-bit ints, whatever) that a test requires. The file is "rewound" when it is exhausted. The total files size is 1 gigabyte. Dieharder was then run on the file with `dieharder -a -g 201 bow-256-4M.bin` to produce the included results file `rainbow-256.txt`. You can see that while most tests pass, some are weak and some fail. I think this is because the file is "too short" for some tests and is rewound. The reason I think this is because when I run it in "open format" (that is, streamed infinitely from rainsum and piped directly to dieharder, rather than through a fixed length file) all occasions for regret disappear. 

- `rainbow-64-infinite.txt`: The source stream was generated with `rainsum -a bow -s 64 -l 4000000000` (which would generate more than enough for a full run of dieharder). The stream was consumed by dieharder using the command: `rainsum dieharder -m stream -a bow -s 64 -l 4000000000 | ./dieharder -a -g 200` (in effect keying the stream generation off of hashing the dieharder binary itself!). This produces the included results file, which, as you can see, evidently passes all tests with 1 weak and NO fail. 

- `rainstorm-64-infinite.txt`: The source stream was generated with `rainsum -a storm -s 64 -l 4000000000` (which would generate more than enough for a full run of dieharder). The stream was consumed by dieharder using the command: `rainsum dieharder -m stream -a storm -s 64 -l 4000000000 | ./dieharder -a -g 200` (in effect keying the stream generation off of hashing the dieharder binary itself!). This produces the included results file, which, as you can see, evidently passes all tests with 2 weak and NO fail.

