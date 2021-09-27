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

# Safety Catch

In order to allow the EDI notifier to send out emails:
- A safety catch needs to be set on the EDI notifier.
- This same safety catch needs to be configured on the Odoo config file and return a truthy value.
```
[email]
edi_notifier_safety_catch=True
```
- If no safety is configured no emails will be sent.
- If only one part of the safety is configured no emails will be sent.
