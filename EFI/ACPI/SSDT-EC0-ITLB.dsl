/*
 * SSDT-EC0-ITLB.dsl — HP Elite Dragonfly G2 (Tiger Lake) Early-Boot EC0.ECRI 8-bit Split Fix
 *
 * Root cause:
 *   During early macOS boot (t ~ 1.63s), AppleACPIEC::start registers its EmbeddedControl
 *   address-space handler and evaluates \_SB.PC00.LPCB.EC0._REG(3, 1) -> ECRI() BEFORE
 *   ECEnabler.kext attaches (t ~ 2.57s, "ECEnabler::init: Primed successfully!").
 *   Stock AppleACPIEC rejects >8-bit EC FieldUnit reads with AE_BAD_PARAMETER.
 *   Inside ECRI(), four methods perform 16-bit EC FieldUnit reads:
 *     1. \_SB.PC00.LPCB.EC0.ITLB (DSDT): reads BFC (Offset 0x8D, 16-bit)
 *     2. \_SB.PC00.LPCB.EC0.EC12 (SSDT2 "NVTEC"): reads ACPR (Offset 0xF9, 16-bit)
 *     3. \_SB.PC00.LPCB.EC0.EC13 (SSDT2 "NVTEC"): reads BDC (Offset 0x89, 16-bit) and BDV (Offset 0x95, 16-bit)
 *     4. \_SB.IETM.ODVP (SSDT14 "DptfTabl"): reads ACPR (0xF9), BDC (0x89), and BDV (0x95)
 *
 * Companion OpenCore ACPI Patches:
 *   1. DSDT:                 49544C42 00 (ITLB\0) -> 58544C42 00 (XTLB\0), Count=1
 *   2. SSDT ("NVTEC"):       45433132 00 (EC12\0) -> 58433132 00 (XC12\0), Count=1
 *   3. SSDT ("NVTEC"):       45433133 00 (EC13\0) -> 58433133 00 (XC13\0), Count=1
 *   4. SSDT ("DptfTabl"):    4F445650 08 (ODVP\x08) -> 58445650 08 (XDVP\x08), Count=1
 */
DefinitionBlock ("", "SSDT", 2, "HPTGL", "EC0ITLB", 0x00001000)
{
    External (_SB_.IETM, DeviceObj)
    External (_SB_.IETM.ODVX, PkgObj)
    External (_SB_.IETM.XDVP, MethodObj)    // 0 Arguments
    External (_SB_.PC00.LPCB.EC0_, DeviceObj)
    External (_SB_.PC00.LPCB.EC0_.BATP, FieldUnitObj)
    External (_SB_.PC00.LPCB.EC0_.ECMX, MutexObj)
    External (_SB_.PC00.LPCB.EC0_.ECRG, IntObj)
    External (_SB_.PC00.LPCB.EC0_.LB1_, FieldUnitObj)
    External (_SB_.PC00.LPCB.EC0_.LB2_, FieldUnitObj)
    External (_SB_.PC00.LPCB.EC0_.NLB1, IntObj)
    External (_SB_.PC00.LPCB.EC0_.NLB2, IntObj)
    External (_SB_.PC00.LPCB.EC0_.XC12, MethodObj)    // 0 Arguments
    External (_SB_.PC00.LPCB.EC0_.XC13, MethodObj)    // 0 Arguments
    External (_SB_.PC00.LPCB.EC0_.XTLB, MethodObj)    // 0 Arguments
    External (G25F, FieldUnitObj)
    External (HPID, FieldUnitObj)
    External (ODV0, IntObj)
    External (ODV1, IntObj)
    External (ODV3, IntObj)
    External (ODV5, IntObj)
    External (ODV6, IntObj)
    External (ODV7, IntObj)
    External (ODV9, IntObj)
    External (ODVB, IntObj)
    External (ODVC, IntObj)

    Scope (\_SB.PC00.LPCB.EC0)
    {
        OperationRegion (ECR2, EmbeddedControl, 0x89, 0x0E)
        Field (ECR2, ByteAcc, NoLock, Preserve)
        {
            BDCL,   8,
            BDCH,   8,
            Offset (0x04),
            BFCL,   8,
            BFCH,   8,
            Offset (0x0C),
            BDVL,   8,
            BDVH,   8
        }

        OperationRegion (ECR3, EmbeddedControl, 0xF9, 0x02)
        Field (ECR3, ByteAcc, NoLock, Preserve)
        {
            ACPL,   8,
            ACPH,   8
        }

        Method (ITLB, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                If (ECRG)
                {
                    Store (Or (ShiftLeft (BFCH, 0x08), BFCL), Local3)
                }
                Else
                {
                    Store (Zero, Local3)
                }

                Multiply (Local3, NLB1, Local0)
                Divide (Local0, 0x64, , Local4)
                Divide (Add (Local4, 0x09), 0x0A, Local0, Local1)
                Multiply (Local3, NLB2, Local0)
                Divide (Local0, 0x64, , Local4)
                Divide (Add (Local4, 0x09), 0x0A, Local0, Local2)
                If (ECRG)
                {
                    Store (Local1, LB1)
                    Store (Local2, LB2)
                }
            }
            ElseIf (CondRefOf (\_SB.PC00.LPCB.EC0.XTLB))
            {
                XTLB ()
            }
        }

        Method (EC12, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Store (Zero, Local0)
                Acquire (ECMX, 0xFFFF)
                If (ECRG)
                {
                    Store (Or (ShiftLeft (ACPH, 0x08), ACPL), Local0)
                }

                Release (ECMX)
                Return (Local0)
            }

            If (CondRefOf (\_SB.PC00.LPCB.EC0.XC12))
            {
                Return (XC12 ())
            }

            Return (Zero)
        }

        Method (EC13, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Store (Zero, Local0)
                Acquire (ECMX, 0xFFFF)
                If (ECRG)
                {
                    Store (Or (ShiftLeft (BDVH, 0x08), BDVL), Local1)
                    Store (Or (ShiftLeft (BDCH, 0x08), BDCL), Local2)
                    Multiply (Local1, Local2, Local0)
                    Divide (Local0, 0x000F4240, Local3, Local0)
                    If (LGreaterEqual (Local3, 0x0007A120))
                    {
                        Increment (Local0)
                    }
                }

                Release (ECMX)
                Return (Local0)
            }

            If (CondRefOf (\_SB.PC00.LPCB.EC0.XC13))
            {
                Return (XC13 ())
            }

            Return (Zero)
        }
    }

    Scope (\_SB.IETM)
    {
        Method (ODVP, 0, Serialized)
        {
            If (_OSI ("Darwin"))
            {
                Store (\ODV0, Index (ODVX, Zero))
                Store (\ODV1, Index (ODVX, One))
                Store (\G25F, Index (ODVX, 0x02))
                Store (\ODV3, Index (ODVX, 0x03))
                Store (And (\HPID, 0xFF), Index (ODVX, 0x04))
                Store (\ODV5, Index (ODVX, 0x05))
                Store (\ODV6, Index (ODVX, 0x06))
                Store (\ODV7, Index (ODVX, 0x07))
                Acquire (\_SB.PC00.LPCB.EC0.ECMX, 0xFFFF)
                If (\_SB.PC00.LPCB.EC0.ECRG)
                {
                    Store (Or (ShiftLeft (\_SB.PC00.LPCB.EC0.ACPH, 0x08), \_SB.PC00.LPCB.EC0.ACPL), Index (ODVX, 0x08))
                }
                Else
                {
                    Store (Zero, Index (ODVX, 0x08))
                }

                Release (\_SB.PC00.LPCB.EC0.ECMX)
                Store (\ODV9, Index (ODVX, 0x09))
                Acquire (\_SB.PC00.LPCB.EC0.ECMX, 0xFFFF)
                If (LAnd (\_SB.PC00.LPCB.EC0.ECRG, LEqual (\_SB.PC00.LPCB.EC0.BATP, One)))
                {
                    Store (Or (ShiftLeft (\_SB.PC00.LPCB.EC0.BDCH, 0x08), \_SB.PC00.LPCB.EC0.BDCL), Local0)
                    Store (Or (ShiftLeft (\_SB.PC00.LPCB.EC0.BDVH, 0x08), \_SB.PC00.LPCB.EC0.BDVL), Local1)
                    Store (Divide (Multiply (Local0, Local1), 0x000F4240, ), Index (ODVX, 0x0A))
                }
                Else
                {
                    Store (Zero, Index (ODVX, 0x0A))
                }

                Release (\_SB.PC00.LPCB.EC0.ECMX)
                Store (\ODVB, Index (ODVX, 0x0B))
                Store (\ODVC, Index (ODVX, 0x0C))
                Return (ODVX)
            }

            If (CondRefOf (\_SB.IETM.XDVP))
            {
                Return (XDVP ())
            }

            Return (ODVX)
        }
    }
}
