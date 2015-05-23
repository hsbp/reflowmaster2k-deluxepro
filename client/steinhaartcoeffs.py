import numpy
import math
import sys

# key: temp in degree Celsisus, value: resistance in Ohms

# datasheet
profile = { 0: 498, 70: 826, 190: 1640, 300: 2624}

#homegrown
#profile = {180: 1564, 220: 1976, 260: 2337, 300: 2788}

a = []
b = []
sampleNo = len(profile)
if sampleNo == 3:
    exps = [0, 1, 3]
elif sampleNo == 4:
    exps = [0, 1, 2, 3]
else:
    raise ValueError("Number of sample points in the profile must be 3 or 4")
for temp, res in profile.items():
    b.append([1 / (temp + 273.15)])
    lnR = math.log(res)
    m = []
    for exp in exps:
        m.append(lnR ** exp)
    a.append(m)

#print(a, b)

[[A], [B], [C], [D]] = numpy.linalg.solve(a, b)

print(A, B, C, D)

if len(sys.argv) > 1:
    r = float(sys.argv[1])
    lnR = math.log(r)
    t = 1 / (A + B * lnR + C * lnR**2 + D * lnR**3) - 273.15
    print(t)