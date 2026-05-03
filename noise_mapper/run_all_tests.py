"""
Test Runner Script for Noise Mapper Project
Runs all test suites and generates comprehensive test report
Usage: python run_all_tests.py
"""

import unittest
import sys
import os
import time
from io import StringIO
import json


class TestResults:
    """Class to collect and format test results"""
    
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None
        
    def start_timing(self):
        self.start_time = time.time()
        
    def end_timing(self):
        self.end_time = time.time()
        
    def add_result(self, test_suite, result):
        self.results.append({
            'suite': test_suite,
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
            'success_rate': (result.testsRun - len(result.failures) - len(result.errors)) / max(result.testsRun, 1) * 100
        })
        
    def print_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "="*80)
        print("NOISE MAPPER TEST SUITE - COMPREHENSIVE RESULTS")
        print("="*80)
        
        total_tests = sum(r['tests_run'] for r in self.results)
        total_failures = sum(r['failures'] for r in self.results)
        total_errors = sum(r['errors'] for r in self.results)
        total_skipped = sum(r['skipped'] for r in self.results)
        
        print(f"📊 OVERALL STATISTICS:")
        print(f"   Total Tests Run: {total_tests}")
        print(f"   ✅ Passed: {total_tests - total_failures - total_errors}")
        print(f"   ❌ Failed: {total_failures}")
        print(f"   🔥 Errors: {total_errors}")
        print(f"   ⏭️  Skipped: {total_skipped}")
        
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            print(f"   ⏱️  Total Duration: {duration:.2f} seconds")
            
        overall_success = (total_tests - total_failures - total_errors) / max(total_tests, 1) * 100
        print(f"   📈 Overall Success Rate: {overall_success:.1f}%")
        
        print(f"\n📋 DETAILED RESULTS BY TEST SUITE:")
        print("-"*80)
        
        for result in self.results:
            status = "✅ PASS" if result['failures'] == 0 and result['errors'] == 0 else "❌ FAIL"
            print(f"{status} {result['suite']:<30} | "
                  f"Tests: {result['tests_run']:<3} | "
                  f"Success: {result['success_rate']:<5.1f}% | "
                  f"Failures: {result['failures']:<2} | "
                  f"Errors: {result['errors']:<2} | "
                  f"Skipped: {result['skipped']:<2}")
                  
        print("\n" + "="*80)
        
        if total_failures > 0 or total_errors > 0:
            print("⚠️  SOME TESTS FAILED - Check output above for details")
            print("💡 TIP: Run individual test files for more detailed error information")
        else:
            print("🎉 ALL TESTS PASSED! Your Noise Mapper is working great!")
            
        print("="*80)


def run_test_suite(test_file, test_name):
    """Run a specific test suite and return results"""
    print(f"\n🔄 Running {test_name}...")
    print("-" * 50)
    
    # Capture output
    test_output = StringIO()
    
    # Load and run the test suite
    loader = unittest.TestLoader()
    
    try:
        # Add the directory to Python path
        test_dir = os.path.dirname(test_file)
        if test_dir and test_dir not in sys.path:
            sys.path.insert(0, test_dir)
            
        # Import the test module
        module_name = os.path.basename(test_file).replace('.py', '')
        
        if test_file.startswith('api/'):
            sys.path.insert(0, 'api')
        elif test_file.startswith('consumer/'):
            sys.path.insert(0, 'consumer')
            
        suite = loader.loadTestsFromName(module_name)
        
        # Run the tests
        runner = unittest.TextTestRunner(stream=test_output, verbosity=2)
        result = runner.run(suite)
        
        # Print the output
        output_content = test_output.getvalue()
        print(output_content)
        
        return result
        
    except ImportError as e:
        print(f"⚠️  Could not import {test_file}: {e}")
        print("💡 Make sure all dependencies are installed and files exist")
        
        # Create a dummy result for missing tests
        result = unittest.TestResult()
        result.testsRun = 0
        return result
        
    except Exception as e:
        print(f"❌ Error running {test_file}: {e}")
        
        # Create a dummy result for failed tests
        result = unittest.TestResult()
        result.testsRun = 0
        result.errors = [("Test Import Error", str(e))]
        return result


def check_dependencies():
    """Check if required dependencies are available"""
    print("🔍 Checking Dependencies...")
    
    required_packages = [
        'flask', 'influxdb', 'folium', 'numpy', 'scipy',
        'paho.mqtt.client', 'requests', 'unittest'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'paho.mqtt.client':
                import paho.mqtt.client
                print(f"   ✅ paho-mqtt")
            else:
                __import__(package.replace('-', '_'))
                print(f"   ✅ {package}")
        except ImportError:
            display_name = 'paho-mqtt' if package == 'paho.mqtt.client' else package
            print(f"   ❌ {display_name} - MISSING")
            missing_packages.append('paho-mqtt' if package == 'paho.mqtt.client' else package)
            
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("💡 Install with: pip install " + ' '.join(missing_packages))
        return False
        
    print("✅ All dependencies available!")
    return True


def main():
    """Main test runner function"""
    print("🚀 NOISE MAPPER COMPREHENSIVE TEST SUITE")
    print("="*50)
    
    # Check dependencies first
    if not check_dependencies():
        print("\n❌ Cannot run tests due to missing dependencies")
        sys.exit(1)
        
    # Initialize results collector
    results = TestResults()
    results.start_timing()
    
    # Define test suites to run from consolidated tests directory
    test_suites = [
        ('tests/test_api_comprehensive.py', 'API Comprehensive Tests'),
        ('tests/test_consumer.py', 'Consumer Comprehensive Tests'),
        ('tests/test_system_integration.py', 'System Integration Tests'),
        ('tests/test_api_basic.py', 'Basic API Tests'),
    ]
    
    # Run each test suite
    for test_file, test_name in test_suites:
        if os.path.exists(test_file):
            result = run_test_suite(test_file, test_name)
            results.add_result(test_name, result)
        else:
            print(f"⚠️  Test file not found: {test_file}")
            
    results.end_timing()
    
    # Print comprehensive summary
    results.print_summary()
    
    # Generate JSON report for CI/CD
    total_duration = 0
    if results.start_time and results.end_time:
        total_duration = results.end_time - results.start_time
        
    json_report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_duration': total_duration,
        'suites': results.results,
        'total_tests': sum(r['tests_run'] for r in results.results),
        'total_failures': sum(r['failures'] for r in results.results),
        'total_errors': sum(r['errors'] for r in results.results),
        'overall_success_rate': sum(r['success_rate'] for r in results.results) / len(results.results) if results.results else 0
    }
    
    with open('test_results.json', 'w') as f:
        json.dump(json_report, f, indent=2)
        
    print(f"\n📄 Detailed results saved to: test_results.json")
    
    # Return appropriate exit code
    total_failures = sum(r['failures'] for r in results.results)
    total_errors = sum(r['errors'] for r in results.results)
    
    if total_failures > 0 or total_errors > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()