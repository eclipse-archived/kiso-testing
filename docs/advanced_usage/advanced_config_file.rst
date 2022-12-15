.. _config_file:


How to make the most of the config file
---------------------------------------

Requirements specification
~~~~~~~~~~~~~~~~~~~~~~~~~~

[optional] - Any package specified will be checked.

Use cases:

- A new feature is introduced and used in the test
- Breaking change introduced with a new release
- Specific package used in a test that does not belong to pykiso

.. literalinclude:: ../../examples/templates/config_features.yaml
    :language: yaml
    :lines: 51-65


Real-World Configuration File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../examples/uart.yaml
    :language: yaml
    :linenos:


Activation of specific loggers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, every logger that does not belong to the `pykiso` package or that is not an `auxiliary`
logger will see its level set to WARNING even if you have in the command line `pykiso --log-level DEBUG`.

This aims to reduce redundant logs from additional modules during the test execution.
For keeping specific loggers to the set log-level, it is possible to set the `activate_log` parameter in the `auxiliary` config.
The following example activates the `jlink` logger from the `pylink` package, imported in `cc_rtt_segger.py`:

.. code:: yaml

  auxiliaries:
    aux1:
      connectors:
        com: rtt_channel
      config:
        activate_log:
        # only specifying pylink will include child loggers
        - pylink.jlink
        - my_pkg
      type: pykiso.lib.auxiliaries.dut_auxiliary:DUTAuxiliary
  connectors:
    rtt_channel:
      config: null
      type: pykiso.lib.connectors.cc_rtt_segger:CCRttSegger

Based on this example, by specifying `my_pkg`, all child loggers will also be set to the set log-level.

.. note:: If e.g. only the logger `my_pkg.module_1` should be set to the level, it should be entered as such.

Ability to use environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible to replace any value by an environment variable in the YAML files.
When using environment variables, the following format should be respected: `ENV{my-env-var}`.
In the following example, an environment variable called `TEST_SUITE_1` contains the path to the test suite 1 directory.

.. literalinclude:: ../../examples/dummy_env_var.yaml
    :language: yaml
    :lines: 22-25

It is also possible to set a default value in case the environment variable is not found.
The following format should be used: `ENV{my-env-var=my_default_value}`.

In the following example, an environment variable called `TEST_SUITE_2` would contain the path to
the test_suite_2 directory. If the variable is not set, the default value will be taken instead.

.. literalinclude:: ../../examples/dummy_env_var.yaml
    :language: yaml
    :lines: 14

Specify files and folders
~~~~~~~~~~~~~~~~~~~~~~~~~

To specify files and folders you can use absolute or relative paths.
Relative paths are always given **relative to the location of the yaml file**.

According to the YAML specification, values enclosed in single quotes are enforced as strings,
and **will not be parsed**.

.. code:: yaml

    example_config:
        # this relative path will not be made absolute
        rel_script_path_unresolved: './script_folder/my_awesome_script.py'
        # this one will
        rel_script_path: ./script_folder/my_awesome_script.py
        abs_script_path_win: C:/script_folder/my_awesome_script.py
        abs_script_path_unix: /home/usr/script_folder/my_awesome_script.py

.. warning::
  Relative path or file locations must always start with `./`.
  If not, it will still be resolved but unexpected behaviour can result from it.

.. _config_sub_yaml:

Include sub-YAMLs
~~~~~~~~~~~~~~~~~

Frequently used configuration parts can be stored in a separate YAML file.
To include this configuration file in the main one, the path to the sub-configuration file has to
be provided, preceded with the `!include` tag.

Relative paths in the sub-YAML file are then resolved **relative to the sub-YAML's location**.

.. literalinclude:: ../../examples/templates/config_features.yaml
    :language: yaml
    :lines: 28-37


Sharing a communication channel between multiple auxiliaries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to attach a single communication channel to multiple defined auxiliaries, it is sufficient
to use the same channel name for all auxiliaries.

Under the hood, ``pykiso`` will automatically create a :py:class:`~pykiso.lib.auxiliaries.proxy_auxiliary.ProxyAuxiliary`
that will have exclusive access to the communication channel. A
:py:class:`~pykiso.lib.connectors.cc_proxy.CCProxy` will be plugged between each declared auxiliary and
the created :py:class:`~pykiso.lib.auxiliaries.proxy_auxiliary.ProxyAuxiliary`. This allows to
keep a minimalistic :py:class:`~pykiso.connector.CChannel` implementation.

An illustration of the resulting internal setup can be found at :ref:`proxy_aux`.

In other words, if you define the following YAML configuration file:

.. code:: yaml
  auxiliaries:
    aux1:
      connectors:
        com: chan1
      config: null
      type: pykiso.lib.auxiliaries.dut_auxiliary:DUTAuxiliary
    aux2:
      connectors:
        com: chan1
      type: pykiso.lib.auxiliaries.communication_auxiliary:CommunicationAuxiliary

  connectors:
    chan1:
      config: null
      type: pykiso.lib.connectors.cc_example:CCExample


Then, ``pykiso`` will internally modify this configuration to become:


.. code:: yaml
  auxiliaries:
    proxy_aux:
      connectors:
        com: chan1
      config:
        aux_list: [aux1, aux2]
      type: pykiso.lib.auxiliaries.proxy_auxiliary:ProxyAuxiliary
    aux1:
      connectors:
        com: cc_proxy_aux1
      config: null
      type: pykiso.lib.auxiliaries.dut_auxiliary:DUTAuxiliary
    aux2:
      connectors:
        com: chan2
      type: pykiso.lib.auxiliaries.communication_auxiliary:CommunicationAuxiliary
    connectors:
      chan1:
        config: null
        type: pykiso.lib.connectors.cc_example:CCExample
      cc_proxy_aux1:
        config: null
        type: pykiso.lib.connectors.cc_proxy:CCProxy
      cc_proxy_aux2:
        config: null
        type: pykiso.lib.connectors.cc_proxy:CCProxy


.. note::
  Keep in mind that an auxiliary connected through a
  :py:class:`~pykiso.lib.auxiliaries.proxy_auxiliary.ProxyAuxiliary`
  will receive the other auxiliaries' messages.


Make a proxy auxiliary trace
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Proxy auxiliary is capable of creating a trace file, where all received messages at connector
level are written. This feature is useful when proxy auxiliary is associated with a connector
who doesn't have any trace capability (in contrast to cc_pcan_can or cc_rtt_segger for example).

Everything is handled at configuration level and especially at yaml file :

.. code:: yaml

  proxy_aux:
    connectors:
      # communication channel alias
      com: <channel-alias>
    config:
      # Auxiliaries alias list bound to proxy auxiliary
      aux_list : [<aux alias 1>, <aux alias 2>, <aux alias 3>]
      # activate trace at proxy level, sniff everything received at
      # connector level and write it in .log file.
      activate_trace : True
      # by default the trace is placed where pykiso is launched
      # otherwise user should specify his own path
      # (absolute and relative)
      trace_dir: ./suite_proxy
      # by default the trace file's name is :
      # YY-MM-DD_hh-mm-ss_proxy_logging.log
      # otherwise user should specify his own name
      trace_name: can_trace
    type: pykiso.lib.auxiliaries.proxy_auxiliary:ProxyAuxiliary


Delay an auxiliary start-up
~~~~~~~~~~~~~~~~~~~~~~~~~~~

All threaded auxiliaries are capable to delay their start-up (not starting at import level).
This means, from user point of view, it's possible to start it on demand and especially where
it's really needed.

.. warning:: in a proxy set-up be sure to always start the proxy auxiliary last
    otherwise an error will occurred due to proxy auxiliary specific import rules

In order to achieved that, a parameter was added at the auxiliary configuration level.

.. code:: yaml

  auxiliaries:
    proxy_aux:
      connectors:
          com: can_channel
      config:
        aux_list : [aux1, aux2]
        activate_trace : True
        trace_dir: ./suite_proxy
        trace_name: can_trace
        # if False create the auxiliary instance but don't start it, an
        # additional call of start method has to be performed.
        # By default, auto_start flag is set to True and "normal" ITF aux
        # creation mechanism is used.
        auto_start: False
      type: pykiso.lib.auxiliaries.proxy_auxiliary:ProxyAuxiliary
    aux1:
      connectors:
          com: proxy_com1
      config:
        auto_start: False
      type: pykiso.lib.auxiliaries.communication_auxiliary:CommunicationAuxiliary
    aux2:
      connectors:
          com: proxy_com2
      config:
        auto_start: False
      type: pykiso.lib.auxiliaries.communication_auxiliary:CommunicationAuxiliary

In user's script simply call the related auxilairy start method:

.. literalinclude:: ../../examples/templates/suite_proxy/test_proxy.py
    :language: python
    :lines: 40-46
