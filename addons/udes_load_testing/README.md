# UDES load testing

Provides load tests for UDES

## Installation

Put udes_stock and udes_load_testing into your addons path.

## Running tests

Load tests can be run using the normal odoo unit tests framework:
To run all tests

``` bash
odoo-bin -d udesloadtest -i udes_stock,udes_load_testing --test-enable
```

or to run a subset use

``` bash
odoo-bin -d udesloadtest -i udes_stock,udes_load_testing --test-file udes_load_testing/test/test_picking.py
```

### Config

To change the steps or repeats you can change add a udes_load_test section to your rc file.
You can specify default values for the parameterized tests and the default number of repeats.
It is also possible to define the parameterize values to be used for individual classes.
This is done by specifying the class's name (case insensitive).
The number of pieces of background data can also be set in the same way, this will only be used by the children of BackgroundDataRunner.

``` plain text
[udes_load_test]
default = [(10,), (100,),]
repeats = 10
background = 200
TestPickLines = [(200,), (300,)]
TestPickLines_repeats = 2
TestOutboundLinesBackGroundData_background = 100
```

These can be accessed through `from .config import config` then `config.TestPickLines`.

## Making new tests

New tests can be made from inheriting from LoadRunner or one of its children. Then write methods (whose names begin with `time_`) for each step of your process.
By adding `time_` to you method name it will be wrapped in a timing decorator.
Then create a test method which calls your `time_` methods and then passes them through to `_process_results`.
This will then add the time it took too run your method into a file called `<classname without Test>_time.csv` which is a tab delimited csv.
N.B: files will be appended.
The filename can be specified directly by setting the _filename attribute before calling `super().setUpClass()`

If you wish to view your results in an ASCII plot, call the `_report` method - this should be done in another test
When using `parameterized`.

