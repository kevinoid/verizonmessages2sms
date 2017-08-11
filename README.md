VerizonMessages2SMS
===================

A Python script to convert text messages stored in the SQLite database of the
[Verizon Messages Windows
App](https://www.microsoft.com/en-us/store/p/verizon-messages/9wzdncrdcsnz)
into XML readable by the [Carbonite SMS Backup & Restore Android
App](https://play.google.com/store/apps/details?id=com.riteshsahu.SMSBackupRestore).

Usage
-----

To import Verizon Messages onto Android:

1.  Install [Verizon
    Messages](https://www.microsoft.com/en-us/store/p/verizon-messages/9wzdncrdcsnz).
2.  Run Verizon Messages and login.
3.  **Important** Scroll through all text messages to import.  The app appears
    to only cache messages in the database once viewed.  If the messages are
    not viewed, they will not be imported.
4.  Close Verizon Messages.
5.  (Optional) Copy the Verizon Messages database from
    `C:\\Users\\<Username>\\AppData\\Local\\Packages\\VerizonWireless.VerizonMessages_40sg4y5zd4vfj\\LocalState\\Database\\Verizon.db`
    to a backup location (or another computer).
6.  Run `./verizonmessages2sms.py -o sms.xml`.  (See `verizonmessages2sms.py
    --help` for additional options and usage information.)
7.  Copy `sms.xml` to the target Android phone.
8.  Install [SMS Backup &
    Restore](https://play.google.com/store/apps/details?id=com.riteshsahu.SMSBackupRestore) on the target Android device.
8.  Run SMS Backup & Restore, choose Restore from the menu, then restore
    messages from the copied file.

Limitations
-----------

This script currently imports MMS messages as SMS messages and discards all
data other than the text body.  This should be fixable, but I didn't have any
MMS messages to test.

License
-------

VerizonMessages2SMS is free software; you can redistribute it and/or modify
it under the terms of the MIT License.
