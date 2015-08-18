# Copyright (c) 2015 Servionica, LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo.config import cfg
from nova import manager
from nova.openstack.common import log as logging
from nova.openstack.common import periodic_task
from stevedore import driver


lb_opts = [
    cfg.StrOpt('threshold_class',
               default='standart_deviation',
               help='Threshold class'),
    cfg.StrOpt('balancer_class',
               default='classic',
               help='Balancer class')
]

CONF = cfg.CONF
LOG = logging.getLogger(__name__)
CONF.register_opts(lb_opts, 'loadbalancer')
CONF.import_opt('scheduler_host_manager', 'nova.scheduler.driver')


SUPPORTED_THRESHOLD_CLASSES = [
    'step_threshold',
    'standart_deviation'
]


SUPPORTED_BALANCER_CLASSES = [
    'classic',
    'minimizeSD'
]


def get_balancer_class(class_name):
    if class_name in SUPPORTED_BALANCER_CLASSES:
        namespace = 'nova.loadbalancer.balancer'
        mgr = driver.DriverManager(namespace, class_name)
        return mgr.driver()
    raise Exception('Setted up class is not supported.')


def get_threshold_class(class_name):
    if class_name in SUPPORTED_THRESHOLD_CLASSES:
        namespace = 'nova.loadbalancer.threshold'
        mgr = driver.DriverManager(namespace, class_name)
        return mgr.driver()
    raise Exception('Setted up class is not supported.')


class LoadBalancer(manager.Manager):
    def __init__(self, *args, **kwargs):
        super(LoadBalancer, self).__init__(service_name='loadbalancer',
                                           *args, **kwargs)
        self.threshold_class = get_threshold_class(
            CONF.loadbalancer.threshold_class)
        self.balancer_class = get_balancer_class(
            CONF.loadbalancer.balancer_class)

    def _balancer(self, context):
        node, nodes, extra_info = self.threshold_class.indicate(context)
        if node:
            return self.balancer_class.balance(context,
                                               node=node,
                                               nodes=nodes,
                                               extra_info=extra_info)

    @periodic_task.periodic_task
    def indicate_threshold(self, context):
        return self._balancer(context)
