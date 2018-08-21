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
    reader = csv.reader(open(filename, 'r').readlines(), delimiter='\t')
    xlabel, ylabel = next(reader)
    for func, n, t in reader:
        data[func.strip(':')][float(n)].append(float(t))

    return data, xlabel, ylabel


if len(sys.argv) >= 2:
    filename = sys.argv[1]
else:
    filename = input('Load test data file: ')

data, xlabel, ylabel = parse_time_file(filename)

for func_name in data:
    nums, times = zip(*sorted(data[func_name].items()))
    stats = [(np.min(t), np.mean(t), np.max(t)) for t in times]
    mins, means, maxs = map(np.array, zip(*stats))
    minmax = (means - mins, maxs - means)
    nums = np.array(nums)
    plt.errorbar(nums, means, label=func_name, yerr=minmax)

    if means.size < 3:
        print("Can't find meaningful correlation for {}".format(func_name))
        continue

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

plt.xlabel(xlabel)
plt.ylabel(ylabel)
xlim = plt.xlim()
ylim = plt.ylim()
plt.xlim(nums.min(), xlim[1])
plt.ylim(0, ylim[1])

print('Close plot to finish')
plt.legend()
plt.show()
