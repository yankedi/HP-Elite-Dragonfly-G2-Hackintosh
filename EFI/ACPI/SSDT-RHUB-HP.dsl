/*
 * Controlled PCH root-hub port-description fallback trial for this HP.
 * Based on Dortania's Darwin-only RHUB _STA technique, pinned template:
 * https://github.com/dortania/Getting-Started-With-ACPI/blob/a954252fe45c4b92e84a7ea927ed30a69bd84497/extra-files/decompiled/SSDT-RHUB.dsl
 *
 * Exact observed path: _SB.PC00.XHCI.RHUB (8086:a0ed, 00:14.0).
 * TXHC/00:0d.0 is a separate control and is deliberately not targeted.
 * This hides the OEM ACPI root-hub description from Darwin; it does not
 * disable the PCI controller. Driver fallback and USB function are untested.
 * It does not repair the earlier HP_XHC_P table-load/HS09 namespace error.
 */
DefinitionBlock ("", "SSDT", 2, "HPDIAG", "RhubPCH", 0x00000001)
{
    External (_SB_.PC00.XHCI.RHUB, DeviceObj)

    Scope (\_SB.PC00.XHCI.RHUB)
    {
        Method (_STA, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Return (Zero)
            }

            Return (0x0F)
        }
    }
}
