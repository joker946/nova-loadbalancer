#!/usr/bin/env python

import numpy as np
import pylab
import matplotlib.pyplot as plt
import json


json_data = open("data.json").read()
parsed_json = json.loads(json_data)
NumOfIter = len(parsed_json)
i = 0
width = 0.35
print parsed_json
for x in parsed_json:
    RAM = []
    CPU = []
    N = len(x)
    ind = np.arange(N)
    for node in x:
        RAM.append(x[node]['mem'])
        CPU.append(x[node]['cpu'])
    pylab.subplot(1, NumOfIter, i+1)
    p1 = plt.bar(ind, RAM, width, color='#800080')
    p2 = plt.bar(ind, CPU, width, color='black', bottom=RAM,)
    plt.title('Iteration '+str(i))
    plt.xticks(ind+width/2, [node for node in x])
    # plt.yticks(np.arange(0.8))
    plt.ylim(0, 1)
    plt.legend((p1[0], p2[0]), ('RAM', 'CPU'), loc=9)
    i += 1
mng = plt.get_current_fig_manager()
mng.resize(*mng.window.maxsize())
plt.show()
