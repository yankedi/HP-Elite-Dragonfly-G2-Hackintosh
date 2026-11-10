// HP PC00.GFX0: identity-only Apple backlight device. No GPU MMIO initialisation.
DefinitionBlock ("", "SSDT", 2, "HPTEST", "PNLF419", 0x00000001)
{
    External (\_SB.PC00.GFX0, DeviceObj)

    Scope (\_SB.PC00.GFX0)
    {
        Device (PNLF)
        {
            Name (_HID, EisaId ("APP0002"))
            Name (_CID, "backlight")
            Name (_UID, 19)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0B)
                }
                Return (Zero)
            }
        }
    }
}
