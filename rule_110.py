import time
from multiprocessing import Process, Pipe, Queue


def timed(f):
    """
    Utility decorator that runs a function and records the execution time.

    Functions with this decorator return (original_result, time_elapsed).
    """
    def timed_func(*args, **kwargs):
        start = time.time()
        result = f(*args, **kwargs)
        end = time.time()
        return (result, end - start)
    return timed_func


def pprint_row(row, true=".", false=" "):
    """
    Pretty-print a row.
    """
    return "|{0}|".format("".join(true if i else false for i in row))


def rule_110(a, b, c):
    """
    Compute the value of a cell in the Rule 110 automata.
    https://en.wikipedia.org/wiki/Rule_110

    Let `n` be the current row and `i` be the current column. This function
    computes the value of the cell (i, n).

    Inputs:
    a - The value of cell (i-1, n-1)
    b - The value of cell (i, n-1)
    c - The value of cell (i+1, n-1)

    Visually:
    n - 2     ................
    n - 1     ........abc.....
    n         .........X......
    n + 1     ................

    For efficiency, we use the boolean expression from the Karnaugh map of the
    ruleset:
             AB
          00 01 11 10
        ---------------
    C 0 |     X  X    |
      1 |  X  X     X |
        ---------------
    """
    return (not c and b) or (c and not (a and b))


###############################################################################
# Standard, single-threaded method


@timed
def standard_method(row, iters):
    """
    Given a tape represented as a row of Booleans, compute (in-place) the next
    row according to the Rule 110 ruleset.

    Assume that the tape wraps around to form a cylinder, i.e. for a tape of
    length `n`, column 0 is adjacent to column 1 and column n-1.

    Inputs:
        row - the inital state of the tape
        iters - the number of iterations to perform

    Returns: The new value of the tape after `iters` iterations.

    Basic strategy: On each iteration, compute the next iteration in-place.
    This is possible because each value only depends on the three values above
    it.
    """
    for _ in range(iters):
        # First column (0)
        leftmost = row[0]
        a, b, c = row[-1], leftmost, row[1]
        row[0] = rule_110(a, b, c)

        # Middle columns (1 ... n-2)
        for i in range(1, len(row)-1):
            a, b, c = b, c, row[i+1]
            row[i] = rule_110(a, b, c)

        # Last column (n-1)
        a, b, c = b, c, leftmost
        row[-1] = rule_110(a, b, c)
    return row


###############################################################################
# Parallel method


def process_section(left_conn, right_conn, queue, row_section, iters, num):
    """
    Apply n iterations of Rule 110 to a section of the tape, using pipes for
    communicaton with the neighboring sessions. Send the final result after n
    iterations into a queue.

    Inputs:
        left_conn - Pipe to send/receive values from the section to the left
        right_conn - Pipe to send/receive values from the section to the right
        queue - Queue to collect final result of this section
        row_section - inital row section for this process to evaluate
        iters - number of iterations to run
        num - unique identifier number of this process

    Each iteration is performed in place.
    """
    # Before the first iteration, we already know the leftmost and
    # rightmost values for our section
    left_conn.send(row_section[0])
    right_conn.send(row_section[-1])

    for _ in range(iters):
        # First col
        a, b, c = left_conn.recv(), row_section[0], row_section[1]
        row_section[0] = rule_110(a, b, c)
        left_conn.send(row_section[0])

        # Middle cols
        for i in range(1, len(row_section)-1):
            a, b, c = b, c, row_section[i+1]
            row_section[i] = rule_110(a, b, c)

        # Last col
        a, b, c = b, c, right_conn.recv()
        row_section[-1] = rule_110(a, b, c)
        right_conn.send(row_section[-1])

    # Push final result into the queue so that it can be collated
    queue.put((num, row_section))
    return


@timed
def naive_parallel_method(row, iters, splits=2):
    """
    Given a tape represented as a row of Booleans, compute the nth row
    according to the Rule 110 ruleset.

    Assume that the tape wraps around to form a cylinder, i.e. for a tape of
    length `x`, column 0 is adjacent to column 1 and column x-1.

    Inputs:
        row - the inital state of the tape
        iters - the number of iterations to perform
        splits - the number of processes to use

    Returns: The new value of the tape after `iters` iterations.

    Strategy: Split the tape into equal-sized sections, giving each one to a
    process. Each process can communicate with the ones two its left and right
    using two-way pipes. The processes can compute the middle portion of their
    tape sections without interacting with each other.

    To compute the 0th and n-1th values of each section, the processes must
    communicate. During each iteration, each process receives from its
    neighbors the value of the two cells on its left and right, in order to
    compute its 0th and nth cells. It then sends its neighbors the values of
    these 0th and n-1th cells, which its neighbors will need on the next
    iteration.

    At the end of `iters` iterations, each process sends its final section of
    the tape into a Queue and the results are aggregated. This would definitely
    be faster with shared memory, but oh well.
    """
    # Queue for processes to send final results
    q = Queue(maxsize=splits)

    # Pipes for each process to communicate with the processes to its immediate
    # left and right
    pipes = [Pipe() for _ in range(splits)]

    # Create processes and divide up the tape into sections
    processes = []
    for i in range(splits):
        # Interleave pipes so that wraparound works properly
        if i == splits - 1:
            left, right = pipes[i][0], pipes[0][1]
            start, end = len(row)/splits * i, len(row)
        else:
            left, right = pipes[i][0], pipes[i+1][1]
            start, end = len(row)/splits * i, len(row)/splits * (i+1)

        # Create process for this section
        p = Process(target=process_section,
                    args=(left, right, q, row[start:end], iters, i))
        processes.append(p)

    for p in processes:
        p.start()

    # Wait for processes to finish and collate results as we go; the process id
    # ensure that we put the results together in the correct order
    for p in processes:
        p.join()

        proc_id, result = q.get()
        for i, v in enumerate(result):
            row[len(row)/splits * proc_id + i] = v
    return row


###############################################################################
# Benchmark tests


def main():
    """
    Run a benchmark test using the example from Wolfram.com
    http://mathworld.wolfram.com/Rule110.html
    """
    iterations = 10000
    inital_state = lambda: [False]*1000 + [True, False]

    std_result, std_elapsed = standard_method(inital_state(), iterations)
    print "Single process method time:", std_elapsed

    par_result, par_elapsed = naive_parallel_method(inital_state(), iterations, splits=4)
    print "Multi-process method time: ", par_elapsed

    # Sanity check
    assert std_result == par_result


if __name__ == '__main__':
    main()
