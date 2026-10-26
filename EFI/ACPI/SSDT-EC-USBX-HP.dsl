/* Candidate for the captured HP PC00 namespace, not an OEM table replacement.
 * Keep the real \_SB.PC00.LPCB.EC0 and all of its methods/regions untouched.
 * The laptop compatibility pattern and generic USB power defaults are based on
 * Dortania Getting-Started-With-ACPI commit
 * 60029d4fff6d56e210e5f682f6dd6508c4bb3343,
 * extra-files/decompiled/SSDT-EC-USBX-LAPTOP.dsl.
 * These USB values are upstream defaults, not measurements of this HP.
 */
DefinitionBlock ("", "SSDT", 2, "HPTGL", "ECUSBX", 0x00000001)
{
    External (\_SB.EC, DeviceObj)
    External (\_SB.PC00.LPCB.EC, DeviceObj)
    External (\_SB.USBX, DeviceObj)

    Scope (\_SB)
    {
        If (!CondRefOf (\_SB.EC) && !CondRefOf (\_SB.PC00.LPCB.EC))
        {
            Device (EC)
            {
                Name (_HID, "ACID0001")
                Method (_STA, 0, NotSerialized)
                {
                    If (_OSI ("Darwin")) { Return (0x0F) }
                    Return (Zero)
                }
            }
        }

        If (!CondRefOf (\_SB.USBX))
        {
            Device (USBX)
            {
                Name (_ADR, Zero)
                Method (_STA, 0, NotSerialized)
                {
                    If (_OSI ("Darwin")) { Return (0x0F) }
                    Return (Zero)
                }

                Method (_DSM, 4, NotSerialized)
                {
                    If (LEqual (Arg2, Zero)) { Return (Buffer (One) { 0x03 }) }
                    Return (Package (0x08)
                    {
                        "kUSBSleepPowerSupply", 0x13EC,
                        "kUSBSleepPortCurrentLimit", 0x0834,
                        "kUSBWakePowerSupply", 0x13EC,
                        "kUSBWakePortCurrentLimit", 0x0834
                    })
                }
            }
        }
    }
}
