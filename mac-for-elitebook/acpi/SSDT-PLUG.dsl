/* HP DSDT 7afb4e66... declares Processor PR00 in Scope (_SB).
 * This new table only attaches the XCPM plugin property on Darwin.
 * It neither replaces the OEM DSDT nor proves Tiger Lake power management.
 */
DefinitionBlock ("", "SSDT", 2, "HPTGL", "PLUG", 0x00000001)
{
    External (\_SB.PR00, ProcessorObj)

    If (_OSI ("Darwin"))
    {
        Scope (\_SB.PR00)
        {
            Method (_DSM, 4, NotSerialized)
            {
                If (LEqual (Arg2, Zero))
                {
                    Return (Buffer (One) { 0x03 })
                }

                Return (Package (0x02)
                {
                    "plugin-type", One
                })
            }
        }
    }
}
