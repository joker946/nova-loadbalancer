#!/usr/bin/env python

import numpy as np
import pylab
import matplotlib.pyplot as plt
import json
import subprocess
import matplotlib.animation as animation


def tratata():
    subprocess.call(["scp",
                     "root@10.5.2.103:/usr/lib/python2.7/site-packages/nova/loadbalancer/data.json",
                     "data.json"])

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
        print len(parsed_json)
        print len(parsed_json[0])
        t = 12
        ind1 = np.arange(1, len(parsed_json[0])*2, 2)
        ind2 = np.arange(0, len(parsed_json[0])*2, 2)
        print len(RAM)
        p1 = plt.bar(ind1, RAM, width, color='#800080')
        p2 = plt.bar(ind2, CPU, width, color='black')
        plt.title('Iteration '+str(i))
        plt.xticks(ind+width/2, [node for node in x])
        # plt.yticks(np.arange(0.8))
        plt.ylim(0, 1)
        plt.legend((p1[0], p2[0]), ('RAM', 'CPU'), loc=9)
        i += 1
    #mng = plt.get_current_fig_manager()
    #mng.resize(*mng.window.maxsize())
    plt.show()
tratata()