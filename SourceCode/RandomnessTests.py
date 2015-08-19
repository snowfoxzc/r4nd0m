import scipy.special as spc
import scipy.fftpack as sff
import numpy.linalg as lng
import scipy.stats as sst
import numpy
import math
import copy
import os


# TODO: Complete the rest of the Randomness Tests
# TODO: Remove expensive 'partitioning approach' to blocks


class Colours:
    """
    Just used to make the standard-out a little bit less ugly
    """
    Pass, Fail, End, Bold, Info, Italics = '\033[92m', '\033[91m', '\033[0m', '\033[1m', '\033[94m', '\x1B[3m'


class RandomnessTester:
    def __init__(self, bin, method, real_data, start_year, end_year):
        """
        Initializes a RandomnessTester object. This object contains the NIST cryptographic tests for randomness [1].
        These tests only work on binary strings. The input data (bin) is a BinaryFrame object. A BinaryFrame object is
        simply a dictionary of lists containing binary strings. Each entry in the dictionary is an independent data set,
        and each binary string in the list represents a different time period. For example,

        bin.data = {    "JSE",      [010101010, 0111101111, 10101010000],
                        "S&P500",   [000000000, 1111111111, 01010101010] ... }

        Each binary string in the list is a sample. These samples are EACH fed through all of the NIST tests and their
        respective p-values are calculated. If ~96% of samples pass, the data set passes the randomness test(s) e.g.

        [1] For more information see - http://csrc.nist.gov/publications/nistpubs/800-22-rev1a/SP800-22rev1a.pdf
        :param bin: this is a "BinaryFrame" object which is a conversion of a pandas DataFrame into a binary dictionary
        """
        self.bin = bin
        self.method = method
        self.real_data = real_data
        self.start_year = start_year
        self.end_year = end_year
        self.epsilon = 0.00001
        self.condition = 0.001

    def get_string(self, p_val):
        """
        This method returns a string based on the p-value
        :param p_val: the p-value generated by a given test
        :return: a string for outputting to the console
        """
        if p_val >= 0:
            if p_val < self.condition:
                return Colours.Fail + "{0:.5f}".format(p_val) + "\t" + Colours.End
            else:
                return Colours.Pass + "{0:.5f}".format(p_val) + "\t" + Colours.End
        else:
            return "{0:.4f}".format(p_val) + "\t" + Colours.End

    def get_aggregate_pval(self, pvals):
        """
        This method applies a chi-squared test on a series of p-values to check their uniformity.
        :param pvals: the list of p-values for a given data set across all the NIST tests
        :return: the aggregate p-value based on the chi-squared test for the p values.
        """
        bin_counts = numpy.zeros(10)
        for p in pvals:
            pos = min(int(math.floor(p * 10)), 9)
            bin_counts[pos] += 1
        chi_squared = 0
        expected_count = len(pvals) / 10
        for bin_count in bin_counts:
            chi_squared += pow(bin_count - expected_count, 2.0) / expected_count
        return spc.gammaincc(9.0 / 2.0, chi_squared / 2.0)

    def get_aggregate_pass(self, pvals):
        """
        This method determines if a data set passed when you look at all the p-values associates with each of the binary
        strings associated with that data set. If the data set passes on ~96% of the samples it passes overall.
        :param pvals: the list of p-values for a given data set across all the NIST tests
        :return: the proportion of samples which passed their tests.
        """
        npvals = numpy.array(pvals)
        return (npvals > self.condition).sum() / len(pvals)

    def print_dates(self, blocks):
        if self.real_data:
            filler = "".zfill(64)
            string_out = filler.replace("0", " ")
            step = (self.end_year - self.start_year) / blocks
            dates = numpy.arange(start=self.start_year, stop=self.end_year, step=step)
            for i in range(blocks):
                start_string = "~" + str(int(dates[i]))
                string_out += start_string + "\t"
            print(string_out)

    def run_test_suite(self, block_size, q_size):
        """
        This method runs all of the tests included in the NIST test suite for randomness
        :param block_size: the length of each block to look at for each bit string
        :param q_size: the size of the matrix to look at for each bit string
        """
        # For each data set in self.bin
        for c in self.bin.columns:
            print(Colours.Bold + "\n\tRunning " + self.bin.method + " based tests on", c + Colours.End, "\n")
            test_names = ["\t01. Monobit Test Results",
                          "\t02. Block Frequency Test",
                          "\t03. Independent Runs Test",
                          "\t04. Longest Runs Test",
                          "\t05. Matrix Rank Test",
                          "\t06. Spectral Test",
                          "\t07. Non Overlapping Patterns"]

            for i in range(len(test_names)):
                length = len(test_names[i])
                space = 40 - length
                filler = "".zfill(space)
                filler = filler.replace("0", " ")
                test_names[i] += filler

            pvals = [[], [], [], [], [], [], [], []]
            pval_strings = ["", "", "", "", "", "", "", ""]

            # Get the samples for the data set
            binary_strings = self.bin.bin_data[c]
            # Run each one of the tests and record the p_values
            for i in range(len(binary_strings)):
                passed_values, p_values, str_data = [], [], binary_strings[i]

                p_val = self.monobit(str_data)
                pval_strings[0] += self.get_string(p_val)
                pvals[0].append(p_val)

                p_val = self.block_frequency(str_data, block_size)
                pval_strings[1] += self.get_string(p_val)
                pvals[1].append(p_val)

                p_val = self.independent_runs(str_data)
                pval_strings[2] += self.get_string(p_val)
                pvals[2].append(p_val)

                p_val = self.longest_runs(str_data)
                pval_strings[3] += self.get_string(p_val)
                pvals[3].append(p_val)

                p_val = self.matrix_rank(str_data, q_size)
                pval_strings[4] += self.get_string(p_val)
                pvals[4].append(p_val)

                p_val = self.spectral(str_data)
                pval_strings[5] += self.get_string(p_val)
                pvals[5].append(p_val)

                p_val = self.non_overlapping_patterns(str_data, "11110000")
                pval_strings[6] += self.get_string(p_val)
                pvals[6].append(p_val)

            # For each sample calculate the aggregate p_value and aggregate pass %
            aggregate_pvals, aggregate_pass = [], []
            for i in range(len(binary_strings)):
                aggregate_pvals.append(self.get_aggregate_pval(pvals[0]))
                aggregate_pass.append(self.get_aggregate_pass(pvals[0]))

                aggregate_pvals.append(self.get_aggregate_pval(pvals[1]))
                aggregate_pass.append(self.get_aggregate_pass(pvals[1]))

                aggregate_pvals.append(self.get_aggregate_pval(pvals[2]))
                aggregate_pass.append(self.get_aggregate_pass(pvals[2]))

                aggregate_pvals.append(self.get_aggregate_pval(pvals[3]))
                aggregate_pass.append(self.get_aggregate_pass(pvals[3]))

                aggregate_pvals.append(self.get_aggregate_pval(pvals[4]))
                aggregate_pass.append(self.get_aggregate_pass(pvals[4]))

                aggregate_pvals.append(self.get_aggregate_pval(pvals[5]))
                aggregate_pass.append(self.get_aggregate_pass(pvals[5]))

                aggregate_pvals.append(self.get_aggregate_pval(pvals[6]))
                aggregate_pass.append(self.get_aggregate_pass(pvals[6]))

            # Print the results to the console
            self.print_dates(len(binary_strings))
            for i in range(len(test_names)):
                pass_string = Colours.Bold + Colours.Fail + "FAIL!\t" + Colours.End
                if aggregate_pass[i] >= 0.96:
                    pass_string = Colours.Bold + Colours.Pass + "PASS!\t" + Colours.End
                if (numpy.array(pvals[i]) == -1.0).sum() > 0:
                    pass_string = Colours.Bold + "SKIP!\t" + Colours.End

                pval_string = Colours.Bold + Colours.Fail + "p=" + "{0:.5f}".format(
                    aggregate_pvals[i]) + "\t" + Colours.End
                if aggregate_pvals[i] > self.condition:
                    pval_string = Colours.Bold + Colours.Pass + "p=" + "{0:.5f}".format(
                        aggregate_pvals[i]) + "\t" + Colours.End
                if (numpy.array(pvals[i]) == -1.0).sum() > 0:
                    pval_string = "p=SKIPPED\t"

                print(test_names[i] + pass_string + pval_string + pval_strings[i])

    def load_test_data(self, data_set):
        """
        This method is used to load in a test-data binary string. These data sets are included in the TestData directory
        :param data_set: the name of the test data set to load e.g. e.csv, pi.csv, etc.
        :return: a raw binary string of the data
        """
        try:
            raw_data = ""
            path = os.path.join(os.getcwd(), os.pardir, "TestData", data_set)
            with open(path, 'r+') as data_set_file:
                for line in data_set_file:
                    raw_data += line.replace("\n", "").replace("\t", "").replace(" ", "")
            return raw_data
        except FileNotFoundError:
            print("File not found", path, "exiting")
            exit(0)

    def generic_checker(self, test_name, expected, function):
        """
        This is a generic method for checking the outputs from one of the tests against known outputs to ensure that the
        test if acting as expected. Essentially it is a unit tester.
        :param test_name: the name of the test being checked
        :param expected: a list of expected p-values
        :param function: a reference to the function being checked
        """
        print("\n\t", Colours.Bold + test_name + Colours.End)
        data_sets = ["pi", "e", "sqrt2", "sqrt3"]
        for i in range(len(data_sets)):
            p_val = function(self.load_test_data(data_sets[i])[:1000000])
            data_set_label = "".zfill(10 - len(data_sets[i])).replace("0", " ")
            if abs(p_val - expected[i]) < self.epsilon:
                print("\t", Colours.Pass + data_sets[i], data_set_label, "\tp expected = ", expected[i],
                      "\tp computed =", "{0:.6f}".format(p_val) + Colours.End)
            else:
                print("\t", Colours.Fail + data_sets[i], data_set_label, "\tp expected = ", expected[i],
                      "\tp computed =", "{0:.6f}".format(p_val) + Colours.End)

    def test_randomness_tester(self):
        """
        This method calls the method calls each one of the checks of the randomness tests contained in this class
        """
        self.monobit_check()
        self.block_frequency_check()
        self.independent_runs_check()
        self.longest_runs_check()
        self.matrix_rank_check()
        self.spectral_check()
        self.non_overlapping_patterns_check()
        self.overlapping_patterns_check()

    def zeros_and_ones_count(self, str_data: str):
        """
        This is just a simple method for counting zeros and ones
        :param str_data: the data from which to count zeros and ones
        :return: nothing.
        """
        ones, zeros = 0, 0
        # If the char is 0 minus 1, else add 1
        for char in str_data:
            if char == '0':
                zeros += 1
            else:
                ones += 1
        print("\t", Colours.Italics + "Count 1 =", ones, "Count 0 =", zeros, Colours.End)

    def monobit(self, bin_data: str):
        """
        Note that this description is taken from the NIST documentation [1]
        [1] http://csrc.nist.gov/publications/nistpubs/800-22-rev1a/SP800-22rev1a.pdf

        The focus of this test is the proportion of zeros and ones for the entire sequence. The purpose of this test is
        to determine whether the number of ones and zeros in a sequence are approximately the same as would be expected
        for a truly random sequence. This test assesses the closeness of the fraction of ones to 1/2, that is the number
        of ones and zeros ina  sequence should be about the same. All subsequent tests depend on this test.

        :param bin_data: a binary string
        :return: the p-value from the test
        """
        count = 0
        # If the char is 0 minus 1, else add 1
        for char in bin_data:
            if char == '0':
                count -= 1
            else:
                count += 1
        # Calculate the p value
        sobs = count / math.sqrt(len(bin_data))
        p_val = spc.erfc(math.fabs(sobs) / math.sqrt(2))
        return p_val

    def monobit_check(self):
        """
        This is a test method for the monobit test method based on the example in the NIST documentation
        """
        expected = [0.578211, 0.953749, 0.811881, 0.610051]
        self.generic_checker("Testing Monobit Test", expected, self.monobit)

    def block_frequency(self, bin_data: str, block_size=128):
        """
        Note that this description is taken from the NIST documentation [1]
        [1] http://csrc.nist.gov/publications/nistpubs/800-22-rev1a/SP800-22rev1a.pdf

        The focus of this tests is the proportion of ones within M-bit blocks. The purpose of this tests is to determine
        whether the frequency of ones in an M-bit block is approximately M/2, as would be expected under an assumption
        of randomness. For block size M=1, this test degenerates to the monobit frequency test.

        :param bin_data: a binary string
        :return: the p-value from the test
        :param block_size: the size of the blocks that the binary sequence is partitioned into
        """
        # Work out the number of blocks, discard the remainder
        num_blocks = math.floor(len(bin_data) / block_size)
        block_start, block_end = 0, block_size
        # Keep track of the proportion of ones per block
        proportion_sum = 0.0
        for i in range(num_blocks):
            # Slice the binary string into a block
            block_data = bin_data[block_start:block_end]
            # Keep track of the number of ones
            ones_count = 0
            for char in block_data:
                if char == '1':
                    ones_count += 1
            pi = ones_count / block_size
            proportion_sum += pow(pi - 0.5, 2.0)
            # Update the slice locations
            block_start += block_size
            block_end += block_size
        # Calculate the p-value
        chi_squared = 4.0 * block_size * proportion_sum
        p_val = spc.gammaincc(num_blocks / 2, chi_squared / 2)
        return p_val

    def block_frequency_check(self):
        """
        This is a test method for the block frequency test method based on the example in the NIST documentation
        """
        expected = [0.380615, 0.211072, 0.833222, 0.473961]
        self.generic_checker("Testing Block Frequency Test", expected, self.block_frequency)

    def independent_runs(self, bin_data: str):
        """
        Note that this description is taken from the NIST documentation [1]
        [1] http://csrc.nist.gov/publications/nistpubs/800-22-rev1a/SP800-22rev1a.pdf

        The focus of this tests if the total number of runs in the sequences, where a run is an uninterrupted sequence
        of identical bits. A run of length k consists of k identical bits and is bounded before and after with a bit of
        the opposite value. The purpose of the runs tests is to determine whether the number of runs of ones and zeros
        of various lengths is as expected for a random sequence. In particular, this tests determines whether the
        oscillation between zeros and ones is either too fast or too slow.

        :param bin_data: a binary string
        :return: the p-value from the test
        """
        ones_count, n = 0, len(bin_data)
        for char in bin_data:
            if char == '1':
                ones_count += 1
        p, vobs = float(ones_count / n), 1
        tau = 2 / math.sqrt(len(bin_data))
        if abs(p - 0.5) > tau:
            return 0.0
        else:
            for i in range(1, n):
                if bin_data[i] != bin_data[i - 1]:
                    vobs += 1
            # expected_runs = 1 + 2 * (n - 1) * 0.5 * 0.5
            # print("\t", Colours.Italics + "Observed runs =", vobs, "Expected runs", expected_runs, Colours.End)
            num = abs(vobs - 2.0 * n * p * (1.0 - p))
            den = 2.0 * math.sqrt(2.0 * n) * p * (1.0 - p)
            p_val = spc.erfc(float(num / den))
            return p_val

    def independent_runs_check(self):
        """
        This is a test method for the runs test method based on the example in the NIST documentation
        """
        expected = [0.419268, 0.561917, 0.313427, 0.261123]
        self.generic_checker("Testing Independent Runs Test", expected, self.independent_runs)

    def longest_runs(self, bin_data: str):
        """
        Note that this description is taken from the NIST documentation [1]
        [1] http://csrc.nist.gov/publications/nistpubs/800-22-rev1a/SP800-22rev1a.pdf

        The focus of the tests is the longest run of ones within M-bit blocks. The purpose of this tests is to determine
        whether the length of the longest run of ones within the tested sequences is consistent with the length of the
        longest run of ones that would be expected in a random sequence. Note that an irregularity in the expected
        length of the longest run of ones implies that there is also an irregularity ub tge expected length of the long
        est run of zeroes. Therefore, only one test is necessary for this statistical tests of randomness

        :param bin_data: a binary string
        :return: the p-value from the test
        """
        if len(bin_data) < 128:
            print("\t", "Not enough data to run test!")
            return -1.0
        elif len(bin_data) < 6272:
            k, m = 3, 8
            v_values = [1, 2, 3, 4]
            pik_values = [0.21484375, 0.3671875, 0.23046875, 0.1875]
        elif len(bin_data) < 75000:
            k, m = 5, 128
            v_values = [4, 5, 6, 7, 8, 9]
            pik_values = [0.1174035788, 0.242955959, 0.249363483, 0.17517706, 0.102701071, 0.112398847]
        else:
            k, m = 6, 10000
            v_values = [10, 11, 12, 13, 14, 15, 16]
            pik_values = [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]

        # Work out the number of blocks, discard the remainder
        # pik = [0.2148, 0.3672, 0.2305, 0.1875]
        num_blocks = math.floor(len(bin_data) / m)
        frequencies = numpy.zeros(k + 1)
        block_start, block_end = 0, m
        for i in range(num_blocks):
            # Slice the binary string into a block
            block_data = bin_data[block_start:block_end]
            # Keep track of the number of ones
            max_run_count, run_count = 0, 0
            for j in range(0, m):
                if block_data[j] == '1':
                    run_count += 1
                    max_run_count = max(max_run_count, run_count)
                else:
                    max_run_count = max(max_run_count, run_count)
                    run_count = 0
            max_run_count = max(max_run_count, run_count)
            if max_run_count < v_values[0]:
                frequencies[0] += 1
            for j in range(k):
                if max_run_count == v_values[j]:
                    frequencies[j] += 1
            if max_run_count > v_values[k - 1]:
                frequencies[k] += 1
            block_start += m
            block_end += m
        # print(frequencies)
        chi_squared = 0
        for i in range(len(frequencies)):
            chi_squared += (pow(frequencies[i] - (num_blocks * pik_values[i]), 2.0)) / (num_blocks * pik_values[i])
        p_val = spc.gammaincc(float(k / 2), float(chi_squared / 2))
        return p_val

    def longest_runs_check(self):
        """
        This is a test method for the longest run test method based on the example in the NIST documentation
        """
        expected = [0.024390, 0.718945, 0.012117, 0.446726]
        self.generic_checker("Testing Longest Runs Test", expected, self.longest_runs)

    def matrix_rank(self, bin_data: str, q=32):
        """
        Note that this description is taken from the NIST documentation [1]
        [1] http://csrc.nist.gov/publications/nistpubs/800-22-rev1a/SP800-22rev1a.pdf

        The focus of the test is the rank of disjoint sub-matrices of the entire sequence. The purpose of this test is
        to check for linear dependence among fixed length sub strings of the original sequence. Note that this test
        also appears in the DIEHARD battery of tests.

        :param bin_data: a binary string
        :return: the p-value from the test
        """
        shape = (q, q)
        n = len(bin_data)
        block_size = int(q * q)
        num_m = math.floor(n / (q * q))
        block_start, block_end = 0, block_size
        # print(q, n, num_m, block_size)

        if num_m > 0:
            max_ranks = [0, 0, 0]
            for im in range(num_m):
                block_data = bin_data[block_start:block_end]
                block = numpy.zeros(len(block_data))
                for i in range(len(block_data)):
                    if block_data[i] == '1':
                        block[i] = 1.0
                m = block.reshape(shape)
                ranker = BinaryMatrix(m, q, q)
                rank = ranker.compute_rank()
                # print(rank)
                if rank == q:
                    max_ranks[0] += 1
                elif rank == (q - 1):
                    max_ranks[1] += 1
                else:
                    max_ranks[2] += 1
                # Update index trackers
                block_start += block_size
                block_end += block_size

            piks = [1.0, 0.0, 0.0]
            for x in range(1, 50):
                piks[0] *= 1 - (1.0 / (2 ** x))
            piks[1] = 2 * piks[0]
            piks[2] = 1 - piks[0] - piks[1]

            chi = 0.0
            for i in range(len(piks)):
                chi += pow((max_ranks[i] - piks[i] * num_m), 2.0) / (piks[i] * num_m)
            p_val = math.exp(-chi / 2)
            return p_val
        else:
            return -1.0

    def matrix_rank_check(self):
        """
        This is a test method for the binary matrix rank test based on the example in the NIST documentation
        """
        expected = [0.083553, 0.306156, 0.823810, 0.314498]
        self.generic_checker("Testing Matrix Rank Test", expected, self.matrix_rank)

    def spectral(self, bin_data: str):
        """
        Note that this description is taken from the NIST documentation [1]
        [1] http://csrc.nist.gov/publications/nistpubs/800-22-rev1a/SP800-22rev1a.pdf

        The focus of this test is the peak heights in the Discrete Fourier Transform of the sequence. The purpose of
        this test is to detect periodic features (i.e., repetitive patterns that are near each other) in the tested
        sequence that would indicate a deviation from the assumption of randomness. The intention is to detect whether
        the number of peaks exceeding the 95 % threshold is significantly different than 5 %.

        :param bin_data: a binary string
        :return: the p-value from the test
        """
        n = len(bin_data)
        plus_minus_one = []
        for char in bin_data:
            if char == '0':
                plus_minus_one.append(-1)
            elif char == '1':
                plus_minus_one.append(1)
        # Product discrete fourier transform of plus minus one
        s = sff.fft(plus_minus_one)
        modulus = numpy.abs(s[0:n / 2])
        tau = numpy.sqrt(numpy.log(1 / 0.05) * n)
        # Theoretical number of peaks
        count_n0 = 0.95 * (n / 2)
        # Count the number of actual peaks m > T
        count_n1 = len(numpy.where(modulus < tau)[0])
        # Calculate d and return the p value statistic
        d = (count_n1 - count_n0) / numpy.sqrt(n * 0.95 * 0.05 / 4)
        p_val = spc.erfc(abs(d) / numpy.sqrt(2))
        return p_val

    def spectral_check(self):
        """
        This is a test method for the spectral test based on the example in the NIST documentation
        """
        expected = [0.010186, 0.847187, 0.581909, 0.776046]
        self.generic_checker("Check Spectral Test", expected, self.spectral)

    def non_overlapping_patterns(self, bin_data: str, pattern="000000001", num_blocks=8):
        """
        Note that this description is taken from the NIST documentation [1]
        [1] http://csrc.nist.gov/publications/nistpubs/800-22-rev1a/SP800-22rev1a.pdf

        The focus of this test is the number of occurrences of pre-specified target strings. The purpose of this
        test is to detect generators that produce too many occurrences of a given non-periodic (aperiodic) pattern.
        For this test and for the Overlapping Template Matching test of Section 2.8, an m-bit window is used to
        search for a specific m-bit pattern. If the pattern is not found, the window slides one bit position. If the
        pattern is found, the window is reset to the bit after the found pattern, and the search resumes.

        :param bin_data: a binary string
        :param pattern: the pattern to match to
        :return: the p-value from the test
        """
        n = len(bin_data)
        pattern_size = len(pattern)
        block_size = math.floor(n / num_blocks)
        pattern_counts = numpy.zeros(num_blocks)
        # For each block in the data
        for i in range(num_blocks):
            block_start = i * block_size
            block_end = block_start + block_size
            block_data = bin_data[block_start:block_end]
            # Count the number of pattern hits
            j = 0
            while j < block_size:
                sub_block = block_data[j:j + pattern_size]
                if sub_block == pattern:
                    pattern_counts[i] += 1
                    j += pattern_size
                else:
                    j += 1
        # Calculate the theoretical mean and variance
        mean = (block_size - pattern_size + 1) / pow(2, pattern_size)
        var = block_size * ((1 / pow(2, pattern_size)) - (((2 * pattern_size) - 1) / (pow(2, pattern_size * 2))))
        # Calculate the Chi Squared statistic for these pattern matches
        chi_squared = 0
        for i in range(num_blocks):
            chi_squared += pow(pattern_counts[i] - mean, 2.0) / var
        # Calculate and return the p value statistic
        p_val = spc.gammaincc(num_blocks / 2, chi_squared / 2)
        return p_val

    def non_overlapping_patterns_check(self):
        """
        This is a test method for the non overlapping patterns test based on the example in the NIST documentation
        """
        expected = [0.165757, 0.496601, 0.569461, 0.532235]
        self.generic_checker("Check Non Overlapping Patterns Test", expected, self.non_overlapping_patterns)

    def overlapping_patterns(self, bin_data: str, pattern_size=9, block_size=1032):
        """
        Note that this description is taken from the NIST documentation [1]
        [1] http://csrc.nist.gov/publications/nistpubs/800-22-rev1a/SP800-22rev1a.pdf

        The focus of the Overlapping Template Matching test is the number of occurrences of pre-specified target
        strings. Both this test and the Non-overlapping Template Matching test of Section 2.7 use an m-bit
        window to search for a specific m-bit pattern. As with the test in Section 2.7, if the pattern is not found,
        the window slides one bit position. The difference between this test and the test in Section 2.7 is that
        when the pattern is found, the window slides only one bit before resuming the search.

        :param bin_data: a binary string
        :param pattern_size: the length of the pattern
        :return: the p-value from the test
        """
        n = len(bin_data)
        pattern = ""
        for i in range(pattern_size):
            pattern += "1"
        num_blocks = math.floor(n / block_size)
        lambda_val = float(block_size - pattern_size + 1) / pow(2, pattern_size)
        eta = lambda_val / 2.0

        piks = [self.get_prob(i, eta) for i in range(5)]
        diff = float(numpy.array(piks).sum())
        piks.append(1.0 - diff)

        pattern_counts = numpy.zeros(6)
        for i in range(num_blocks):
            block_start = i * block_size
            block_end = block_start + block_size
            block_data = bin_data[block_start:block_end]
            # Count the number of pattern hits
            pattern_count = 0
            j = 0
            while j < block_size:
                sub_block = block_data[j:j + pattern_size]
                if sub_block == pattern:
                    pattern_count += 1
                j += 1
            if pattern_count <= 4:
                pattern_counts[pattern_count] += 1
            else:
                pattern_counts[5] += 1

        chi_squared = 0.0
        for i in range(len(pattern_counts)):
            chi_squared += pow(pattern_counts[i] - num_blocks * piks[i], 2.0) / (num_blocks * piks[i])
        return spc.gammaincc(5.0/2.0, chi_squared/2.0)

    def get_prob(self, u, x):
        out = 1.0 * numpy.exp(-x)
        if u != 0:
            out = 1.0 * x * numpy.exp(2*-x) * (2**-u) * spc.hyp1f1(u + 1, 2, x)
        return out

    def overlapping_patterns_check(self):
        """
        This is a test method for the non overlapping patterns test based on the example in the NIST documentation
        """
        expected = [0.296897, 0.110434, 0.791982, 0.082716]
        self.generic_checker("Check Overlapping Patterns Test", expected, self.overlapping_patterns)


class BinaryMatrix:
    def __init__(self, matrix, rows, cols):
        """
        This class contains the algorithm specified in the NIST suite for computing the **binary rank** of a matrix.
        :param matrix: the matrix we want to compute the rank for
        :param rows: the number of rows
        :param cols: the number of columns
        :return: a BinaryMatrix object
        """
        self.M = rows
        self.Q = cols
        self.A = matrix
        self.m = min(rows, cols)

    def compute_rank(self, verbose=False):
        """
        This method computes the binary rank of self.matrix
        :param verbose: if this is true it prints out the matrix after the forward elimination and backward elimination
        operations on the rows. This was used to testing the method to check it is working as expected.
        :return: the rank of the matrix.
        """
        if verbose:
            print("Original Matrix\n", self.A)

        i = 0
        while i < self.m - 1:
            if self.A[i][i] == 1:
                self.perform_row_operations(i, True)
            else:
                found = self.find_unit_element_swap(i, True)
                if found == 1:
                    self.perform_row_operations(i, True)
            i += 1

        if verbose:
            print("Intermediate Matrix\n", self.A)

        i = self.m - 1
        while i > 0:
            if self.A[i][i] == 1:
                self.perform_row_operations(i, False)
            else:
                if self.find_unit_element_swap(i, False) == 1:
                    self.perform_row_operations(i, False)
            i -= 1

        if verbose:
            print("Final Matrix\n", self.A)

        return self.determine_rank()

    def perform_row_operations(self, i, forward_elimination):
        """
        This method performs the elementary row operations. This involves xor'ing up to two rows together depending on
        whether or not certain elements in the matrix contain 1's if the "current" element does not.
        :param i: the current index we are are looking at
        :param forward_elimination: True or False.
        """
        if forward_elimination:
            j = i + 1
            while j < self.M:
                if self.A[j][i] == 1:
                    self.A[j, :] = (self.A[j, :] + self.A[i, :]) % 2
                j += 1
        else:
            j = i - 1
            while j >= 0:
                if self.A[j][i] == 1:
                    self.A[j, :] = (self.A[j, :] + self.A[i, :]) % 2
                j -= 1

    def find_unit_element_swap(self, i, forward_elimination):
        """
        This given an index which does not contain a 1 this searches through the rows below the index to see which rows
        contain 1's, if they do then they swapped. This is done on the forward and backward elimination
        :param i: the current index we are looking at
        :param forward_elimination: True or False.
        """
        row_op = 0
        if forward_elimination:
            index = i + 1
            while index < self.M and self.A[index][i] == 0:
                index += 1
            if index < self.M:
                row_op = self.swap_rows(i, index)
        else:
            index = i - 1
            while index >= 0 and self.A[index][i] == 0:
                index -= 1
            if index >= 0:
                row_op = self.swap_rows(i, index)
        return row_op

    def swap_rows(self, i, ix):
        """
        This method just swaps two rows in a matrix. Had to use the copy package to ensure no memory leakage
        :param i: the first row we want to swap and
        :param ix: the row we want to swap it with
        :return: 1
        """
        temp = copy.copy(self.A[i, :])
        self.A[i, :] = self.A[ix, :]
        self.A[ix, :] = temp
        return 1

    def determine_rank(self):
        """
        This method determines the rank of the transformed matrix
        :return: the rank of the transformed matrix
        """
        rank = self.m
        i = 0
        while i < self.M:
            all_zeros = 1
            for j in range(self.Q):
                if self.A[i][j] == 1:
                    all_zeros = 0
            if all_zeros == 1:
                rank -= 1
            i += 1
        return rank


def test_binary_matrix():
    """
    This is just a silly method for testing the matrix rank class. It is redundant since the Binary Matrix Rank test
    passes the unit tests on the test data anyway ... still useful to keep around though.
    :return:
    """
    data = [1, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 1,
            1, 0, 0, 0, 0, 1,
            1, 0, 1, 0, 1, 0,
            0, 0, 1, 0, 1, 1,
            0, 0, 0, 0, 1, 0]
    m = numpy.array(data)
    m = m.reshape((6, 6))
    ranker = BinaryMatrix(m, 6, 6)
    print(ranker.compute_rank(verbose=True))


if __name__ == '__main__':
    rng_tester = RandomnessTester(None, "discretize", False, 00, 00)
    rng_tester.check_tests()
