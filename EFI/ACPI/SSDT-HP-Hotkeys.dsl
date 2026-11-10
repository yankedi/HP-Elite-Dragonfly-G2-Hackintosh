/*
 * SSDT-HP-Hotkeys — EC _Q86/_Q87 Brightness & WMIV.GVWE Fn Hotkey Bridge for HP Elite Dragonfly G2 (8716)
 *
 * Forwards EC queries _Q86/_Q87 (paired with _Q86->XQ86, _Q87->XQ87 renames) and
 * HP WMI events in \_SB.WMIV.GVWE (paired with GVWE->XVWE rename) to PS2K scan codes
 * on Darwin so VoodooPS2Keyboard and hp-bridge receive all top-row Fn hotkeys natively.
 */
DefinitionBlock ("", "SSDT", 2, "HPQOEM", "HPHOTKEY", 0x00001000)
{
    External (_SB_.PC00.LPCB.EC0_, DeviceObj)
    External (_SB_.PC00.LPCB.EC0_.XQ86, MethodObj)    // 0 Arguments
    External (_SB_.PC00.LPCB.EC0_.XQ87, MethodObj)    // 0 Arguments
    External (_SB_.PC00.LPCB.PS2K, DeviceObj)
    External (_SB_.WMIV, DeviceObj)
    External (_SB_.WMIV._WED, MethodObj)    // 1 Arguments
    External (_SB_.WMIV.XVWE, MethodObj)    // 2 Arguments

    Scope (\_SB.PC00.LPCB.EC0)
    {
        Method (_Q86, 0, NotSerialized)  // _Qxx: EC Query, xx=0x00-0xFF
        {
            If (_OSI ("Darwin"))
            {
                Notify (\_SB.PC00.LPCB.PS2K, 0x0417)
            }

            If (CondRefOf (\_SB.PC00.LPCB.EC0.XQ86))
            {
                XQ86 ()
            }
        }

        Method (_Q87, 0, NotSerialized)  // _Qxx: EC Query, xx=0x00-0xFF
        {
            If (_OSI ("Darwin"))
            {
                Notify (\_SB.PC00.LPCB.PS2K, 0x0412)
            }

            If (CondRefOf (\_SB.PC00.LPCB.EC0.XQ87))
            {
                XQ87 ()
            }
        }
    }

    Scope (\_SB.WMIV)
    {
        Method (GVWE, 2, Serialized)
        {
            If (CondRefOf (\_SB.WMIV.XVWE))
            {
                XVWE (Arg0, Arg1)
            }

            If (_OSI ("Darwin"))
            {
                If (CondRefOf (\_SB.WMIV._WED))
                {
                    _WED (0x81)
                }

                If (((Arg0 == 0x14) || (Arg0 == 0x04)))
                {
                    Local0 = (Arg1 & 0xFFFF)
                    Local1 = (Local0 & 0xFF)
                    If ((((Local1 == 0xFE) || (Local1 == 0xFF)) || ((Local1 ==
                        0xFD) || (Local0 == 0x21A4))))
                    {
                        Notify (\_SB.PC00.LPCB.PS2K, 0x0403)
                    }
                    ElseIf (((Local0 == 0x02) || (Local0 == 0x0200)))
                    {
                        Notify (\_SB.PC00.LPCB.PS2K, 0x0417)
                    }
                    ElseIf (((Local0 == 0x03) || (Local0 == 0x0300)))
                    {
                        Notify (\_SB.PC00.LPCB.PS2K, 0x0412)
                    }
                    ElseIf (((Local0 == 0x0270) || (Local0 == 0x7002)))
                    {
                        Notify (\_SB.PC00.LPCB.PS2K, 0x046E)
                    }
                    ElseIf ((((Local0 == 0x20E6) || (Local0 == 0x21A5)) || ((
                        Local0 == 0x21A8) || ((Local0 == 0x20E8) || (Local0 == 0x2142)))))
                    {
                        Notify (\_SB.PC00.LPCB.PS2K, 0x0368)
                    }
                }
            }
        }
    }
}
