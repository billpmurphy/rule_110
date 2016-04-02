Python code to run [Rule 110](http://mathworld.wolfram.com/Rule110.html)
sequentially and in parallel.

I wrote this because I was wondering how much of a speedup you get from
executing Rule 110 in parallel processes, given that a lot of communication
between processes is necessary because of how the rules work. As it turns out,
there is still a substandial speedup from using multiple processes even for
pretty small inputs (>1000-cell tape with a few thousand iterations).

The file `rule_110.py` contains two implementations of Rule 110 (one that runs
in a single process, one that runs in multiple processes) and a simple
benchmark test that you can play with.

Coming soon, maybe:
* Re-implementation in a lower-level language (C or Rust) with shared memory
* Additional parallelization algorithm that I have in mind, which is greedier
  than the one implemented here
