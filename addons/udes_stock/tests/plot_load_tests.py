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
    data = defaultdict(lambda: defaultdict(list))
    for func, n, t in csv.reader(open(filename, 'r').readlines(),
                                 delimiter='\t'):
        data[func.strip(':')][float(n)].append(float(t))

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

    definitely_template = '{name} is definitely {adjective} than linear:\n' \
        '\tarea: {area}'
    possibly_template = '{name} is possibly {adjective} than linear:\n' \
        '\tcoefficient: {coefficient}\n' \
        '\tpval: {pval}\n' \
        '\tarea: {area}'

    if coefficient > COEFFICIENT_THRESHOLD and pval < PVAL_THRESHOLD:
        print(definitely_template.format(
            adjective='worse',
            name=func_name,
            area=area))
    elif coefficient < -COEFFICIENT_THRESHOLD and pval < PVAL_THRESHOLD:
        print(definitely_template.format(
            adjective='better',
            name=func_name,
            area=area))
    elif coefficient > COEFFICIENT_THRESHOLD:
        print(possibly_template.format(
            adjective='worse',
            coefficient=coefficient,
            pval=pval,
            area=area,
            name=func_name))
    elif coefficient < -COEFFICIENT_THRESHOLD:
        print(possibly_template.format(
            adjective='better',
            coefficient=coefficient,
            pval=pval,
            area=area,
            name=func_name))
    else:
        print('no correlation found for {} '
              'so probably linear'.format(func_name))

plt.xlabel('Number of move lines')
plt.ylabel('Average time taken/s')
xlim = plt.xlim()
ylim = plt.ylim()
plt.xlim(nums.min(), xlim[1])
plt.ylim(0, ylim[1])

print('Close plot to finish')
plt.legend()
plt.show()
