#!/usr/bin/env python
#
# Copyright (c) 2014, Oracle and/or its affiliates. All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#

"""
This file contains the replication synchronization checker utility. It is used
to check the data consistency between main and subordinates (and synchronize the
data if requested by the user).
"""

from mysql.utilities.common.tools import check_python_version

# Check Python version compatibility
check_python_version()

import os
import sys

from mysql.utilities.command.rpl_admin import skip_subordinates_trx
from mysql.utilities.common.messages import PARSE_ERR_OPTS_REQ
from mysql.utilities.common.options import (add_subordinates_option, add_verbosity,
                                            check_gtid_set_format,
                                            check_password_security,
                                            setup_common_options)
from mysql.utilities.common.tools import check_connector_python
from mysql.utilities.common.topology import parse_topology_connections
from mysql.utilities.exception import UtilError, UtilRplError

# Check for connector/python
if not check_connector_python():
    sys.exit(1)

# Constants
NAME = "MySQL Utilities - mysqlsubordinatetrx"
DESCRIPTION = "mysqlsubordinatetrx - skip transactions on subordinates"
USAGE = "%prog --gtid-set=gtid_set --subordinates=user:pass@host:port"
EXTENDED_HELP = """
Introduction
------------
The mysqlsubordinatetrx utility is designed to skip multiple transactions on subordinates
in a quick and easy way. More specifically, it injects empty transactions
on the subordinates for each GTID that will be skipped.

The utility requires GTIDs to be enabled on all subordinates. It does not require
replication to be stopped. However, in some situation it is recommended.
For example, in order to skip a transaction from the main  on a subordinate, that
subordinate should be stopped otherwise the target transaction might still be
replicated (and not skipped).

Note: Only transactions (GTIDs) that were not committed can be skipped, since
two transactions cannot be applied with the same GTID. GTIDs already in the
GTID_EXECUTED set of a subordinate will be ignored.

The utility requires the specification of the GTID set to skip and the list of
target subordinates as shown in the following example.

  # Skip the specified GTID set (three transaction: 10, 11, 12) on two subordinates.

  $ mysqlsubordinatetrx --gtid-set=ee2655ae-2e88-11e4-b7a3-606720440b68:10-12 \\
                  --subordinates=rpl:pass@host2:3306,rpl:pass@host3:3306

Helpful Hints
-------------
  - Use the --dryrun option to execute the utility in dry run mode and confirm
    which transactions would be skipped with the provided input values without
    effectively skipping them.

WARNING: Skipping transactions is a useful technique to recover from erroneous
situations with replication. However, it must be applied with extreme caution
and with full knowledge of its consequences as it might lead to data
inconsistencies between the replication servers. For example, if a transaction
that insert some data 'row1' in table 't1' fails on one subordinate and that
transaction is skipped to solve the issue, then that data will be missing from
the subordinate (and no longer replicated). As a consequence the data for table 't1'
will be inconsistent with the one on the main and the other subordinates because
'row1' will be missing.

"""

if __name__ == '__main__':
    # Setup the command parser with common options (excluding --).
    parser = setup_common_options(os.path.basename(sys.argv[0]),
                                  DESCRIPTION, USAGE, server=False,
                                  extended_help=EXTENDED_HELP, add_ssl=True)

    # Add option for the GTID set to skip..
    parser.add_option("--gtid-set", action="store", dest="gtid_set",
                      type="string", default=None,
                      help="set of Global Transaction Identifiers (GTID) to "
                           "skip.")

    # Add the --subordinates option.
    add_subordinates_option(parser)

    # Add option for the dry run mode.
    parser.add_option("--dryrun", action="store_true", dest="dry_run",
                      default=False,
                      help="determine the transactions (GTID) to be skipped "
                           "for each subordinate but without effectively skipping "
                           "them (injecting empty transactions) - useful to "
                           "test the transactions that would be skipped.")

    # Add verbosity option (no --quite option).
    add_verbosity(parser, False)

    # Parse the options and arguments.
    opt, args = parser.parse_args()

    # Check security settings
    check_password_security(opt, args)

    # Options --gtid-set and --subordinates options are required.
    if not opt.gtid_set:
        parser.error(PARSE_ERR_OPTS_REQ.format(opt='--gtid-set'))
    if not opt.subordinates:
        parser.error(PARSE_ERR_OPTS_REQ.format(opt='--subordinates'))

    # Check GTID set format.
    check_gtid_set_format(parser, opt.gtid_set)

    # Parse the connection parameters for the subordinates (no candidates).
    try:
        opt.main = None  # No main option available, set value to None.
        _, subordinates_val, _ = parse_topology_connections(
            opt, parse_candidates=False
        )
    except UtilRplError:
        _, err, _ = sys.exc_info()
        sys.stderr.write("ERROR: {0}\n".format(err.errmsg))
        sys.exit(1)

    # Create dictionary of options
    options = {
        'verbosity': 0 if opt.verbosity is None else opt.verbosity,
        'dry_run': opt.dry_run,
    }

    # Skip transactions for the given list of subordinates.
    try:
        skip_subordinates_trx(opt.gtid_set, subordinates_val, options)
    except UtilError:
        _, err, _ = sys.exc_info()
        sys.stderr.write("ERROR: {0}\n".format(err.errmsg))
        sys.exit(1)
