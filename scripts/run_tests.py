import os
import re
import sys
import argparse
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Constants for directory paths.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DESIGN_DIR = os.path.join(ROOT_DIR, "designs")
TEST_DIR = os.path.join(ROOT_DIR, "tests")
CELL_LIBRARY_PATH = os.path.join(TEST_DIR, "SAED32_lib")

OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")
TRANSCRIPT_DIR = os.path.join(LOGS_DIR, "transcript")
COMPILATION_DIR = os.path.join(LOGS_DIR, "compilation")
WAVES_DIR = os.path.join(OUTPUT_DIR, "waves")

LIBRARY_DIR = os.path.join(ROOT_DIR, "TESTS")

# Test mapping for subdirectories and file ranges.
TEST_MAPPING = {
    "simple": range(0, 2),
    "move": range(2, 15),
    "logic": range(15, 29)
}

# Stores the add wave command for a range of tests for better performance.
_wave_command_cache = {}

def parse_arguments():
    """Parse and validate command-line arguments.

    This function defines the arguments available for the script,
    validates them, and provides a help message for the user.

    Returns:
        argparse.Namespace: Parsed arguments from the command line.
    """
    parser = argparse.ArgumentParser(description="Run testbenches in various modes.")

    # Argument for specifying the testbench number (optional, can be None).
    parser.add_argument("-n", "--number", type=int, nargs="?", default=None,
                        help="Specify the testbench number to run (e.g., 1 for test_1). If not provided, the script will run all available tests.")
    
    # Argument for specifying a range of tests to run (inclusive).
    parser.add_argument("-r", "--range", type=int, nargs=2, metavar=("START", "END"),
                        help="Test range to run (inclusive, e.g., -r 2 10).")
    
    # Argument for specifying the debugging mode.
    parser.add_argument("-m", "--mode", type=int, choices=[0, 1, 2, 3], default=0,
                        help="Debugging mode: 0=Command-line, 1=Save waves, 2=GUI, 3=View saved waves.")
        
    # Parse the arguments from the command line.
    args = parser.parse_args()

    return args

def setup_directories():
    """Ensure necessary directories exist for logs, compilation, waves, etc.

    This function creates all required directories (logs, transcripts, compilation,
    waveform output, and the library). If the directories already exist, they are
    not recreated.

    Raises:
        OSError: If a directory cannot be created.
    """
    # Paths for all required directories (using pathlib for better cross-platform compatibility)
    directories = [Path(OUTPUT_DIR), Path(LOGS_DIR), Path(TRANSCRIPT_DIR), Path(COMPILATION_DIR), Path(WAVES_DIR), Path(LIBRARY_DIR)]

    # Ensure all required directories exist
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def get_wave_command(test_num):
    """Generate the command for waveform signals based on the test number.

    Args:
        test_num (int): The test number to determine the required signals.

    Returns:
        str: A string containing the waveform command for the selected signals.
    """
    # Define ranges for test numbers with their associated default signals.
    if test_num == 0:
        key = 0
        default_signals = ["iDUT/clk", "iDUT/RST_n", "iDUT/TX", "iDUT/RX", "iRMT/resp", "iRMT/resp_rdy"]
    elif test_num == 1:
        key = 1
        default_signals = ["iDUT/clk", "iDUT/RST_n", "iDUT/cal_done", "iPHYS/iNEMO/NEMO_setup", "iDUT/iTC/send_resp", "iRMT/resp", "iRMT/resp_rdy"]
    elif 2 <= test_num <= 14:
        key = (2, 14)
        default_signals = [
            "iDUT/clk", "iDUT/RST_n", "iPHYS/xx", "iPHYS/yy", "iDUT/iNEMO/heading", "iPHYS/heading_robot", "iDUT/iCMD/desired_heading", "iPHYS/omega_sum",
            "iPHYS/cntrIR_n", "iDUT/iCMD/lftIR", "iDUT/iCMD/cntrIR", "iDUT/iCMD/rghtIR", "iDUT/iCMD/error_abs",
            "iDUT/iCMD/square_cnt", "iDUT/iCMD/move_done", "iDUT/iTC/state", "iDUT/iTC/send_resp", "iRMT/resp",
            "iRMT/resp_rdy", "iDUT/iTC/mv_indx", "iDUT/iTC/move", "iDUT/iCMD/pulse_cnt", "iDUT/iCMD/state"
        ]
    else: # test_num >= 15
        key = (15, float('inf'))
        default_signals = [
            "iDUT/clk", "iDUT/RST_n", "iPHYS/xx", "iPHYS/yy", "iDUT/iNEMO/heading", "iPHYS/heading_robot", "iDUT/iCMD/desired_heading", "iPHYS/omega_sum",
            "iPHYS/cntrIR_n", "iDUT/iCMD/lftIR", "iDUT/iCMD/cntrIR", "iDUT/iCMD/rghtIR", "iDUT/iCMD/error_abs",
            "iDUT/iCMD/square_cnt", "iDUT/iCMD/move_done", "iDUT/iTC/state", "iDUT/iTC/send_resp", "iRMT/resp",
            "iRMT/resp_rdy", "iDUT/iTC/mv_indx", "iDUT/iTC/move", "iDUT/iCMD/pulse_cnt", "iDUT/iCMD/state",
            "iDUT/iCMD/tour_go", "iDUT/iTL/done", "iDUT/fanfare_go", "iDUT/ISPNG/state"
        ]

    # Check if the result for this range is cached.
    if key in _wave_command_cache:
        wave_command = _wave_command_cache[key]
    else:
        # Cache the wave command if it doesn't exist.
        wave_command = " ".join([f"add wave {signal};" for signal in default_signals])
        _wave_command_cache[key] = wave_command

    # Return the cached or newly generated waveform command.
    return wave_command

def validate_solution(log_file):
    """
    Validates if the log file coordinates match the computed Knight's Tour solution.

    This function reads a log file containing a Knight's Tour starting position 
    and a sequence of board coordinates. It then computes a valid Knight's Tour 
    from the given starting position and compares it with the sequence from the log file.

    Args:
        log_file (str): Path to the log file containing the Knight's Tour data.

    Returns:
        str: "success" if the log file coordinates match the computed solution, 
             "error" otherwise.
    """
    def extract_data_from_log(file_path):
        """
        Extracts the starting position and sequence of coordinates from the log file.

        The log file is expected to have a specific format:
        - The starting position is identified by the line: 
          "KnightsTour starting at coordinate: (x, y)"
        - The board coordinates are identified by lines:
          "Coordinate on the board: (x, y)"

        Args:
            file_path (str): Path to the log file.

        Returns:
            tuple: A tuple containing:
                   - start_position (tuple): The starting coordinate (x, y).
                   - coordinates (list): A list of board coordinates in the solution.

        Raises:
            ValueError: If the starting position or coordinates are not found in the log file.
        """
        with open(file_path, 'r') as file:
            lines = file.readlines()

        start_position = None
        coordinates = []

        for line in lines:
            # Extract the starting position
            if "KnightsTour starting at coordinate:" in line:
                match = re.search(r'\((\d+),\s*(\d+)\)', line)
                if match:
                    start_position = (int(match.group(1)), int(match.group(2)))

            # Extract each coordinate on the board
            elif "Coordinate on the board:" in line:
                match = re.search(r'\((\d+),\s*(\d+)\)', line)
                if match:
                    coordinates.append((int(match.group(1)), int(match.group(2))))

        if start_position is None:
            raise ValueError("Starting position not found in the log file.")

        if not coordinates:
            raise ValueError("No coordinates found in the log file.")

        return start_position, coordinates

    def compute_knights_tour(start_position, rows=5, cols=5):
        """
        Computes the Knight's Tour solution starting from the given position.

        This uses a depth-first search (DFS) algorithm to find a valid Knight's Tour.

        Args:
            start_position (tuple): Starting position (x, y) of the Knight.
            rows (int): Number of rows on the chessboard. Default is 5.
            cols (int): Number of columns on the chessboard. Default is 5.

        Returns:
            list: A list of coordinates representing the Knight's Tour.

        Raises:
            ValueError: If no valid Knight's Tour solution exists from the starting position.
        """
        visited_squares = [[0 for _ in range(cols)] for _ in range(rows)]
        solution_path = []

        def get_valid_moves(square):
            """
            Returns all valid moves from a given square.

            Args:
                square (tuple): Current position (x, y) of the Knight.

            Returns:
                list: A list of valid moves (x, y).
            """
            x, y = square
            moves = [
                (x + 1, y + 2), (x - 1, y + 2),
                (x - 2, y + 1), (x - 2, y - 1),
                (x - 1, y - 2), (x + 1, y - 2),
                (x + 2, y - 1), (x + 2, y + 1)
            ]
            return [
                (nx, ny)
                for nx, ny in moves
                if 0 <= nx < rows and 0 <= ny < cols and not visited_squares[nx][ny]
            ]

        def dfs(square, move_count=1):
            """
            Performs depth-first search to find a valid Knight's Tour.

            Args:
                square (tuple): Current position (x, y) of the Knight.
                move_count (int): Current move count. Default is 1.

            Returns:
                bool: True if a valid solution is found, False otherwise.
            """
            x, y = square
            visited_squares[x][y] = 1
            solution_path.append(square)

            if move_count == rows * cols:
                return True

            for move in get_valid_moves(square):
                if dfs(move, move_count + 1):
                    return True

            visited_squares[x][y] = 0
            solution_path.pop()
            return False

        if not dfs(start_position):
            raise ValueError("No valid Knight's Tour solution exists from the starting position.")

        return solution_path

    try:
        # Extract the starting position and Knight's Tour coordinates from the log file.
        start_position, log_coordinates = extract_data_from_log(log_file)

        # Compute the solution for the Knight's Tour starting at the given position.
        computed_solution = compute_knights_tour(start_position)

        # Trim the starting position from the computed solution for comparison.
        computed_solution_trimmed = computed_solution[1:]

        # Compare the computed solution with the coordinates from the log file.
        if log_coordinates == computed_solution_trimmed:
            return "success"
        else:
            return "error"
    except ValueError:
        return "unknown"

def check_logs(test_num, logfile, mode):
    """Check the status of a log file based on the specified mode.

    Args:
        test_num (int): The test number to identify the specific test.
        logfile (str): Path to the log file.
        mode (str): Mode of checking, either "t" for transcript or "c" for compilation.

    Returns:
        str: The result of the log check, either "success", "error", or "unknown".
    """
    def check_compilation(log_file):
        """Check the compilation log for errors or warnings.

        Args:
            log_file (str): Path to the compilation log file.

        Returns:
            str: Returns "error" if any errors are found, "warning" if warnings are present, or "success" if no issues are found.
        """
        # Open and read the content of the log file
        with open(log_file, "r") as file:
            content = file.read()

            # Check for the presence of "Error:" or "Warning:"
            if "Error:" in content:
                return "error"
            elif "Warning:" in content:
                return "warning"
            else:
                return "success"

    def check_transcript(test_num, log_file):
        """Check the simulation transcript for success or failure.

        Args:
            test_num (int): The test number to identify the specific test.
            log_file (str): Path to the simulation transcript log file.

        Returns:
            str: Returns "success" if the test passed, "error" if there was an error, or "unknown" if the status is not determined.
        """
        # Open and read the content of the transcript log file.
        with open(log_file, "r") as file:
            content = file.read()

            # Check for specific success or failure strings in the transcript.
            if "ERROR" in content:
                return "error"
            elif test_num <= 15:
                if "YAHOO!! All tests passed." in content:
                    return "success"
                else: 
                    return "unknown"
            else:
                return validate_solution(log_file)
                
        # If no status is found, return unknown.
        return "unknown"

    # Direct to the appropriate check function based on the mode
    if mode == "t":
        return check_transcript(test_num, logfile)
    elif mode == "c":
        return check_compilation(logfile)

def compile_files(test_num, test_path):
    """Compile the required files for the test simulation.

    Args:
        test_num (int): The test number to identify the test for compilation.
        test_path (str): The path to the test file to be compiled.

    Raises:
        SystemExit: If compilation fails, the program exits with an error.
    """
    # Define the path for the compilation log.
    log_file = os.path.join(COMPILATION_DIR, f"compilation_{test_num}.log")

    # Determine the files to compile based on the test number.
    if test_num != 0:
        all_files = f"../designs/pre_synthesis/*.sv ../tests/*.sv {test_path}"
    else:
        all_files = f"-timescale=1ns/1ps ../tests/*.sv ../designs/pre_synthesis/UART.sv ../designs/pre_synthesis/*_r* ../designs/pre_synthesis/*_tx* ../designs/post_synthesis/*.vg {test_path}"
    
    # Attempt to compile the files.
    with open(log_file, 'w') as log_fh:
        try:            
            # If the work library for that test does not exist we form a create library command with vlib.
            if not Path(f"./TEST_{test_num}").is_dir():
                compile_command = f"vsim -c -logfile {log_file} -do 'vlib TEST_{test_num}; vlog -work TEST_{test_num} -vopt -stats=none {all_files}; quit -f;'"
            else:
                compile_command = f"vlog -logfile {log_file} -work TEST_{test_num} -vopt -stats=none {all_files}"
            subprocess.run(compile_command, shell=True, stdout=log_fh, stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError:
            print(f"Compilation failed for {test_path}. Check the log file for details: {log_file}")
            sys.exit(1)  # Exit the program if compilation fails.

    # Check if the compilation was successful or not.
    result = check_logs(test_num, log_file, "c")

    # Provide feedback on the compilation result.
    if result == "warning":
        print(f"Compilation has warnings for {test_path}. Check the log file for details: {log_file}")
    elif result == "error":
        print(f"Compilation failed for {test_path}. Check the log file for details: {log_file}")
        sys.exit(1)  # Exit the program if compilation fails.

def get_gui_command(test_num, log_file, args):
    """
    Generate the simulation command for GUI-based waveform viewing.

    Args:
        test_num (int): The test number to identify the specific test.
        log_file (str): Path to the log file where simulation output will be saved.
        args (argparse.Namespace): Parsed command-line arguments, including mode and test-specific settings.

    Returns:
        str: The complete simulation command string to execute for GUI mode.
    """
    wave_file = os.path.join(WAVES_DIR, f"KnightsTour_tb_{test_num}.wlf")
    wave_format_file = os.path.join(WAVES_DIR, f"KnightsTour_tb_{test_num}.do")

    # Generate waveform command based on the test arguments.
    add_wave_command = get_wave_command(test_num)

    # Construct the simulation command with necessary flags for waveform generation.
    if test_num == 0:
        sim_command = (
            f"vsim -wlf {wave_file} TEST_{test_num}.KnightsTour_tb -logfile {log_file} -t ns "
            f"-Lf {CELL_LIBRARY_PATH} -voptargs='+acc' -do '{add_wave_command} run -all; "
            f"write format wave -window .main_pane.wave.interior.cs.body.pw.wf {wave_format_file}; "
            f"log -flush /*;'"
        )
    else:
        sim_command = (
            f"vsim -wlf {wave_file} TEST_{test_num}.KnightsTour_tb -logfile {log_file} -voptargs='+acc' -do '{add_wave_command} run -all; "
            f"write format wave -window .main_pane.wave.interior.cs.body.pw.wf {wave_format_file}; log -flush /*;'"
        )

    # Adjust for mode 0 or 1 to ensure the simulation quits after completion.
    if args.mode == 0 or args.mode == 1:
        sim_command = sim_command[:-1] + " quit -f;'"

    return sim_command

def run_simulation(test_num, test_name, log_file, args):
    """Run the simulation based on the selected mode.
    Args:
        test_num (int): The test number to identify the specific test.
        test_name (str): The name of the test (used for logging and messages).
        log_file (str): Path to the log file where simulation output will be saved.
        args (argparse.Namespace): Parsed command-line arguments, including mode and test-specific settings.

    Returns:
        str: The result of the simulation, typically "success", "error", or "unknown".
    """
    # Precompute the simulation command based on the mode.
    if args.mode == 0:
        if args.number is not None and args.range is None:
            print(f"{test_name}: Running in command-line mode...")

        # Base simulation command.
        sim_command = f"vsim -c TEST_{test_num}.KnightsTour_tb -logfile {log_file} -do 'run -all; log -flush /*; quit -f;'"
        
        # Modify the command for test 0.
        if test_num == 0:
            sim_command = f"vsim -c TEST_0.KnightsTour_tb -logfile {log_file} -t ns " \
                    f"-Lf {CELL_LIBRARY_PATH} -do 'run -all; log -flush /*; quit -f;'"        
    else:
        if args.mode == 1: # Save waveforms and log in file.
            if args.number is not None and args.range is None:
                print(f"{test_name}: Saving waveforms and logging to file...")
        elif args.mode == 2: # GUI mode.
            if args.number is not None and args.range is None:
                print(f"{test_name}: Running in GUI mode...")

        sim_command = get_gui_command(test_num, log_file, args)

    # Execute the simulation command and log the output.
    with open(log_file, 'w') as log_fh:
        subprocess.run(sim_command, shell=True, stdout=log_fh, stderr=subprocess.STDOUT, check=True)

    # Check simulation result and return status.
    return check_logs(test_num, log_file, "t")

def run_test(subdir, test_file, args):
    """Run a specific testbench by compiling and executing the simulation.

    Args:
        subdir (str): The subdirectory where the test file is located.
        test_file (str): The test file to be compiled and executed.
        args (argparse.Namespace): Parsed command-line arguments, including mode and test-specific settings.

    Returns:
        None: This function prints status messages based on the test result.
    """
    # Determine the full path to the test file.
    test_path = os.path.join(TEST_DIR, subdir, test_file)
    test_name = os.path.splitext(test_file)[0]
    log_file = os.path.join(TRANSCRIPT_DIR, f"{test_name}.log")
    os.chdir(LIBRARY_DIR)

    # Extract the test number from the test name (if it exists).
    test_num = int(re.search(r'\d+', test_name).group()) if re.search(r'\d+', test_name) else None

    # Step 1: Compile the testbench.
    compile_files(test_num, test_path)

    # Step 2: Run the simulation and handle different modes.
    result = run_simulation(test_num, test_name, log_file, args)
    
    # Output the result of the test based on the simulation result.
    if result == "success":
        print(f"{test_name}: YAHOO!! All tests passed.")
    elif result == "error":
        if args.mode == 0:
            print(f"{test_name}: Test failed. Saving waveforms for later debug...")
            debug_command = get_gui_command(test_num, log_file, args)
            with open(log_file, 'w') as log_fh:
                subprocess.run(debug_command, shell=True, stdout=log_fh, stderr=subprocess.STDOUT, check=True)
        elif args.mode == 1:
            print(f"{test_name}: Test failed. Debug logs saved to {log_file}.")
    elif result == "unknown":
        print(f"{test_name}: Unknown status. Check the log file saved to {log_file}.")

def view_waveforms(test_number):
    """View previously saved waveforms for a specific test.

    Args:
        test_number (int): The test number to view waveforms for.

    Returns:
        None: This function executes the simulation command to view waveforms.
    """
    # Change to the wave directory and view the saved waveforms
    with open(f"./transcript_{test_number}", 'w') as transcript:
        os.chdir(WAVES_DIR)
        print(f"KnightsTour_tb_{test_number}: Viewing saved waveforms...")
        sim_command = f"vsim -view KnightsTour_tb_{test_number}.wlf -do KnightsTour_tb_{test_number}.do;"
        subprocess.run(sim_command, shell=True, stdout=transcript, stderr=subprocess.STDOUT, check=True)

def execute_tests(args):
    """Execute tests based on parsed arguments.

    This function handles the execution of tests based on the provided arguments. 
    It can run a specific test, a range of tests, or all tests, and supports different 
    modes for running tests (command-line, saving, or GUI mode). It also manages 
    parallel execution of tests and waveform viewing.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
    """
    def get_tests_in_range(start, end):
        """Collect test files for a given range of tests.

        Args:
            start (int): The starting test number.
            end (int): The ending test number.

        Returns:
            list: A list of tuples containing the subdirectory and test file for each test in the range.
        """
        return [
            (subdir, f"KnightsTour_tb_{i}.sv")
            for subdir, test_range in TEST_MAPPING.items()
            for i in test_range if start <= i <= end
        ]

    def collect_all_tests():
        """Collect all available test files.

        This function collects all test files that match the naming convention 
        'KnightsTour_tb_*.sv' from all subdirectories in the test directory.

        Returns:
            list: A list of tuples containing the subdirectory and test file for all available tests.
        """
        return [
            (subdir, test_file)
            for subdir in TEST_MAPPING.keys()
            for test_file in os.listdir(os.path.join(TEST_DIR, subdir))
            if test_file.startswith("KnightsTour_tb")
        ]

    def run_parallel_tests(tests):
        """Run multiple tests in parallel using threads.

        Args:
            tests (list): A list of tuples containing the subdirectory and test file to run.

        This function uses a ThreadPoolExecutor to run tests concurrently, improving the speed of I/O-bound operations.
        """
        with ThreadPoolExecutor(max_workers=18) as executor:  # Increased worker count
            futures = [executor.submit(run_test, subdir, test_file, args) for subdir, test_file in tests]
            for future in futures:
                try:
                    future.result()  # Will raise an exception if any occurred
                except Exception as e:
                    print(f"Test failed with error: {e}")

    def view_parallel_waves(test_numbers):
        """View waveforms for multiple tests in parallel using threads.

        Args:
            test_numbers (list): A list of test numbers for which to view the waveforms.

        This function uses a ThreadPoolExecutor to view waveforms concurrently, improving the speed of I/O-bound operations.
        """
        with ThreadPoolExecutor(max_workers=18) as executor:  # Increased worker count
            futures = [executor.submit(view_waveforms, i) for i in test_numbers]
            for future in futures:
                try:
                    future.result()  # Will raise an exception if any occurred
                except Exception as e:
                    print(f"Waveform view failed with error: {e}")

    def run_specific_test(test_num):
        """Run a specific test by its number.

        Args:
            test_num (int): The test number to run.

        This function looks up the test based on the test number and runs it if found.
        If the test is not found, it prints an error message.
        """
        test = get_tests_in_range(test_num, test_num)
        if test:
            run_test(test[0][0], test[0][1], args)
        else:
            print(f"Test {test_num} not found.")

    def handle_mode_3(test_range=None):
        """Handle waveform viewing in mode 3.

        Args:
            test_range (list, optional): A list of test numbers to view waveforms for. If None, all tests are shown.

        This function is responsible for viewing waveforms for tests in parallel. If a range is provided, it views 
        waveforms for the specified tests; otherwise, it views waveforms for all tests.
        """
        if test_range:
            view_parallel_waves(test_range)
        else:
            all_tests = [i for subdir, test_range in TEST_MAPPING.items() for i in test_range]
            view_parallel_waves(all_tests)

    # Handle different cases based on parsed arguments
    if args.number is not None:
        # If a specific test number is provided, run that test
        if args.mode == 3:
            # Mode 3: View waveforms for the specific test
            handle_mode_3([args.number])
        else:
            # Run the specific test
            run_specific_test(args.number)
    elif args.range is not None:
        # If a range of tests is provided, run all tests in that range
        start, end = args.range
        if args.mode == 3:
            # Mode 3: View waveforms for the test range
            handle_mode_3(list(range(start, end + 1)))
        else:
            # Print a message based on the selected mode and range
            mode_messages = {
                0: f"Running all tests from {start} to {end} in command-line mode...",
                1: f"Running all tests from {start} to {end} in saving mode...",
                2: f"Running all tests from {start} to {end} in GUI mode..."
            }
            print(mode_messages.get(args.mode, "Running tests..."))

            # Collect and run the tests in the specified range
            tests = get_tests_in_range(start, end)
            run_parallel_tests(tests)  # Parallel execution for faster results
    else:
        # If no specific test or range is provided, run all tests
        if args.mode == 3:
            handle_mode_3()
        else:
            mode_messages = {
                0: "Running all tests in command-line mode...",
                1: "Running all tests in saving mode...",
                2: "Running all tests in GUI mode..."
            }
            print(mode_messages.get(args.mode, "Running tests..."))

            # Collect and run all tests
            tests = collect_all_tests()
            run_parallel_tests(tests)  # Parallel execution for faster results

def main():
    """Main function to parse arguments, set up directories, and execute tests.

    This function is the entry point for the test execution process. It performs the following tasks:
    - Parses the command-line arguments using `parse_arguments`.
    - Ensures necessary directories exist using `setup_directories`.
    - Executes the tests based on the parsed arguments using `execute_tests`.
    - Prints a completion message once all tests are finished.

    Args:
        None
    """
    # Parse the command-line arguments.
    args = parse_arguments()

    # Set up necessary directories for test execution (logs, transcripts, etc.).
    setup_directories()

    # Execute the tests based on the parsed arguments.
    execute_tests(args)

    # Print completion message after all tests are done.
    print("All tests completed.")

if __name__ == "__main__":
    main()
