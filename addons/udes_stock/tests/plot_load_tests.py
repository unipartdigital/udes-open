import numpy as np
from scipy.stats import spearmanr
from collections import defaultdict
from matplotlib import pyplot as plt
import sys
import csv

COEFFICIENT_THRESHOLD = 0.7
PVAL_THRESHOLD = 0.001

def scaling_coefficient(x, y):
    """Finds if the element wise derivative is increasing or decreasing"""
    dydx = np.diff(y)/np.diff(x)
    coefficient, pval = spearmanr(x[1:], dydx)
    area = np.sum(dydx - dydx[0])
    return area, coefficient, pval


def parse_time_file(filename):
    lines = open(filename, 'r').read()
    data = defaultdict(lambda: defaultdict(list))

    for line in filter(lambda l: len(l) > 0 and '=' not in l,
                       lines.split('\n')):
        func, n, t = line.split('\t')
        data[func.strip(':')][int(n)].append(float(t))

    return data


if len(sys.argv) >= 2:
    filename = sys.argv[1]
else:
    filename = input('Load test data file: ')

data = parse_time_file(filename)

for func_name in data:
    nums, times = zip(*sorted(data[func_name].items()))
    times = np.array(times)
    means = times.mean(axis=1)
    minmax = (means - times.min(axis=1), times.max(axis=1) - means)
    nums = np.array(nums)
    plt.errorbar(nums, means, label=func_name, yerr=minmax)

    area, coefficient, pval = scaling_coefficient(nums, means)

    definitely_worse_template = '{name} is definitely worse than linear:\n'
        '\tarea: {area}'
    possibly_worse_template = '{name} is possibly worse than linear:\n'
        '\tcoefficient: {coefficient}\n'
        '\tpval: {pval}\n'
        '\tarea: {area}'

    if coefficient > COEFFICIENT_THRESHOLD and pval < PVAL_THRESHOLD:
        print(definitely_worse_template.format(
            name=func_name,
            area=area))
    elif coefficient < -COEFFICIENT_THRESHOLD and pval < PVAL_THRESHOLD:
        print(definitely_worse_template.format(
            name=func_name,
            area=area))
    elif coefficient > COEFFICIENT_THRESHOLD:
        print(possibly_worse_template.format(
            coefficient=coefficient,
            pval=pval,
            area=area,
            name=func_name))
    elif coefficient < -COEFFICIENT_THRESHOLD:
        print(possibly_worse_template.format(
            coefficient=coefficient,
            pval=pval,
            area=area,
            name=func_name))
    else:
        print('no correlation found for {}'.format(func_name))

plt.xlabel('Number of move lines')
plt.ylabel('Average time taken/s')
xlim = plt.xlim()
ylim = plt.ylim()
plt.xlim(nums.min(), xlim[1])
plt.ylim(0, ylim[1])

plt.legend()
plt.show()
