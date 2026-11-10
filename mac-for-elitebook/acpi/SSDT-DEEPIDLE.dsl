/*
 * SSDT-DEEPIDLE — Modern Standby (S0ix / Apple Deep Idle) for HP Elite Dragonfly G2 (8716)
 *
 * 1. Defines \_SB.LPS0 and \_GPE.LXEN (Darwin only) so AppleACPIPlatform
 *    publishes IOPMDeepIdleSupported = Yes and selects sleep type 7
 *    (kIOPMSleepTypeDeepIdle, XNU acpi_idle_kernel()).
 * 2. Overrides \_SB.PEPD._STA (paired with MS-SSDT _STA -> XSTA rename)
 *    so \_SB.PEPD (INT33A1 / PNP0D80) attaches in IOACPIPlane on Darwin
 *    with S0ID = 1, without requiring a global XOSI patch.
 * 3. Clears \USWE = Zero on Darwin (in \_SB.LID._INI, \_SB.LPS0, and
 *    \_SB.PEPD._STA) so \_SB.PC00.XHCI._PRW returns { 0x6D, Zero } and
 *    disables USB wake in ACPI without touching GPRW or non-Darwin OSes.
 */
DefinitionBlock ("", "SSDT", 2, "HPS0IX", "DEEPIDLE", 0x00001000)
{
    External (\S0ID, FieldUnitObj)
    External (\USWE, FieldUnitObj)
    External (\_SB.LID, DeviceObj)
    External (\_SB.SLPB, DeviceObj)
    External (\_SB.PEPD, DeviceObj)
    External (\_SB.PEPD.XSTA, MethodObj)

    Scope (\_SB)
    {
        Method (LPS0, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                \USWE = Zero
                Return (One)
            }

            Return (Zero)
        }
    }

    Scope (\_GPE)
    {
        Method (LXEN, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Return (One)
            }

            Return (Zero)
        }
    }

    Scope (\_SB.LID)
    {
        Method (_INI, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                \USWE = Zero
            }
        }

        Method (_PRW, 0, NotSerialized)
        {
            Return (Package (0x02)
            {
                0x6E,
                0x04
            })
        }

        Method (PRW0, 0, NotSerialized)
        {
            Return (Package (0x02)
            {
                0x6E,
                0x04
            })
        }

        Method (_S0W, 0, NotSerialized)
        {
            Return (0x04)
        }
    }

    Scope (\_SB.SLPB)
    {
        Method (_PRW, 0, NotSerialized)
        {
            Return (Package (0x02)
            {
                0x6E,
                0x04
            })
        }

        Method (PRW0, 0, NotSerialized)
        {
            Return (Package (0x02)
            {
                0x6E,
                0x04
            })
        }

        Method (_S0W, 0, NotSerialized)
        {
            Return (0x04)
        }
    }

    Scope (\_SB.PEPD)
    {
        Method (_STA, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                S0ID = One
                \USWE = Zero
                Return (0x0F)
            }

            Return (XSTA ())
        }
    }
}
