/*
 * SSDT-LIDWAKE.dsl — Darwin-only _PRW(0x6E, 0x03) on \_SB.LID for HP Elite Dragonfly G2 (8716)
 *
 * Enables native AppleACPILid WakeOnLid / lidwake and lets AppleACPIPlatform
 * mark EC GPE 0x6E wake-capable so _AcpiHwEnableAllWakeupGpes() arms GPE0_EN[0x6E]
 * right before pmCPUHalt(3) in Deep Idle. Guarded by top-level _OSI ("Darwin")
 * (matching SSDT-PLUG.dsl) so Windows and Linux ACPI namespaces are untouched.
 */
DefinitionBlock ("", "SSDT", 2, "HPLID", "LIDWAKE", 0x00001000)
{
    External (\_SB.LID, DeviceObj)

    If (_OSI ("Darwin"))
    {
        Scope (\_SB.LID)
        {
            Method (_PRW, 0, NotSerialized)
            {
                Return (Package (0x02)
                {
                    0x6E,
                    0x03
                })
            }
        }
    }
}
