# EDI Notifier

Provides a functionality to send email on execution of an `edi.document` or on a
time based trigger

## Features of this module

- EDI notifiers
- email base templates for the notifiers

# Core Data Models

## `edi.notifier`:

The record describing the notifier instance

## `edi.notifier.model`:

Base class for all notifier models

## `edi.notifier.email`:

Base class for notifiers which send emails

## `edi.notifier.email.state`:

Base class for notifier models which check the state

## `edi.notifier.email.success/failed`:

Classes which sends an email when an document successfully/fails executing

## `edi.notifier.email.missing`:

Checks if a transfer with doc type exists between the start of the day and the trigger `time` of the crons attached and that it has not already been reported on

## `edi.notifier.email.missing.in.range`:

Checks if a transfer with doc type exists within the number of `lookback_hours` to
the trigger `time` of the crons attached and that it has not already been reported on
