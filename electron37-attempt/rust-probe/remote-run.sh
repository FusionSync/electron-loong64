#!/bin/sh
set +e
/tmp/hello-no-init
rc=$?
echo remote_rc=$rc
exit 0
