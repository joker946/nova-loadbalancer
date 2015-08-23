import psycopg2
import json
from psycopg2.extras import RealDictCursor
import dateutil.parser
import math

from datetime import datetime


def calculate_sd(hosts, param):
    mean = reduce(lambda res, x: res + hosts[x][param],
                  hosts, 0) / len(hosts)
    variaton = float(reduce(
        lambda res, x: res + (hosts[x][param] - mean) ** 2,
        hosts, 0)) / len(hosts)
    sd = math.sqrt(variaton)
    return sd


def calculate_cpu(instance, compute_nodes=None):
    if not instance['prev_cpu_time']:
        instance['prev_cpu_time'] = 0
    if instance['prev_cpu_time'] > instance['cpu_time']:
        instance['prev_cpu_time'] = 0
    delta_cpu_time = instance['cpu_time'] - instance['prev_cpu_time']
    delta_time = (
        dateutil.parser.parse(instance['updated_at']) - dateutil.parser.parse(
            instance['prev_updated_at']))\
        .seconds
    if compute_nodes:
        num_cpu = 8
    else:
        num_cpu = instance['vcpus']
    if delta_time:
        cpu_load = float(delta_cpu_time) / \
            (float(delta_time) * (10 ** 7) * num_cpu)
        cpu_load = round(cpu_load, 2)
        return cpu_load
    return 0


def fill_compute_stats(instances, compute_nodes):
    host_loads = {}
    for instance in instances:
            cpu_util = calculate_cpu(instance, compute_nodes)
            if instance['host'] in host_loads:
                host_loads[instance['host']]['mem'] += instance['mem']
                host_loads[instance['host']]['cpu'] += cpu_util
            else:
                host_loads[instance['host']] = {}
                host_loads[instance['host']]['mem'] = instance['mem']
                host_loads[instance['host']]['cpu'] = cpu_util
    for node in compute_nodes:
        if node['hypervisor_hostname'] not in host_loads:
            host_loads[node['hypervisor_hostname']] = {}
            host_loads[node['hypervisor_hostname']]['mem'] = 0
            host_loads[node['hypervisor_hostname']]['cpu'] = 0
    return host_loads


def calculate_host_loads(compute_nodes, compute_stats):
    host_loads = compute_stats
    for node in compute_nodes:
        host_loads[node['hypervisor_hostname']]['mem'] \
            /= float(node['memory_total'])
        host_loads[node['hypervisor_hostname']]['cpu'] \
            /= 100.00
    return host_loads


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError("Type not serializable")


def fetch_info():
    res_json = []
    instance_stats = []
    compute_stats = []
    conn = psycopg2.connect(database='nova', user='nova', password='nova')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT instance_stats.instance_uuid, instance_stats.cpu_time,'
                ' instance_stats.prev_cpu_time, instance_stats.mem, '
                'instance_stats.updated_at, instance_stats.prev_updated_at, '
                'instance_stats.block_dev_iops, '
                'instance_stats.prev_block_dev_iops, instances.vcpus, '
                'instances.task_state, instances.host from instance_stats '
                'JOIN instances '
                'ON instance_stats.instance_uuid = instances.uuid '
                'WHERE instances.vm_state = %s;', ('active',))
    res = cur.fetchall()
    for r in res:
        instance_stats.append(r)

    res_json.append({'instances': instance_stats})

    cur.execute('SELECT cs.memory_total, cs.cpu_used_percent, '
                'cs.memory_used, compute_nodes.hypervisor_hostname FROM '
                '(SELECT compute_id, max(created_at) as maxup '
                'from compute_node_stats group by compute_id) as x '
                'inner join compute_node_stats as cs '
                'on cs.compute_id = x.compute_id and cs.created_at = x.maxup '
                'inner join compute_nodes on '
                'cs.compute_id = compute_nodes.id;')
    res = cur.fetchall()
    for r in res:
        compute_stats.append(r)

    res_json.append({'compute_nodes': compute_stats})
    with open('/usr/lib/python2.7/site-packages/nova/loadbalancer/input.json', 'w') as outfile:
        json.dump(res_json, outfile, default=json_serial)
    cur.close()


def make_stats():
    fetch_info()
    input_data = json.load(open('/usr/lib/python2.7/site-packages/nova/loadbalancer/input.json'))
    instances = input_data[0]['instances']
    compute_nodes = input_data[1]['compute_nodes']
    a = fill_compute_stats(instances, compute_nodes)
    a = [calculate_host_loads(compute_nodes, a)]
    data = json.load(open('/usr/lib/python2.7/site-packages/nova/loadbalancer/data.json'))
    data.extend(a)
    if len(data) > 5:
        data = data[1:]
    with open('/usr/lib/python2.7/site-packages/nova/loadbalancer/data.json', 'w') as output:
        json.dump(data, output)
