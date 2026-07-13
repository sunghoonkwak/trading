# Scheduler interface runner

`runner.py` owns schedule registration and its background lifecycle. It
registers the injected portfolio report at 07:00 KST, the order report at
07:00 US/Eastern converted to KST, periodic rebalancing every five minutes,
and daily DST rescheduling.

`start()` clears old jobs and does not create a second thread. `stop()` signals
the loop, clears jobs, and joins briefly. Manual order triggers delegate only
to the injected order runner.
