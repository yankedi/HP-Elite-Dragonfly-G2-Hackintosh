/*
 * SSDT-BATFULL.dsl — HP Elite Dragonfly G2 (8716) Battery Full-Charge Clamp for macOS
 *
 * Root cause:
 *   HP Tiger Lake ECs frequently stop charging slightly below Last Full Charge
 *   Capacity (_BIX[3]), leaving _BST[0] with neither charging (bit 1) nor
 *   discharging (bit 0) set. SMCBatteryManager only sets FullyCharged = Yes
 *   when Remaining >= LastFull; otherwise powerd / PowerUIAgent schedule
 *   frequent dark wakes (GaugingMitigationActions / com.apple.obc).
 *
 * DSDT verification (HP 8716 raw DSDT, 261046 bytes):
 *   - \_SB.BAT0 (DSDT.dsl:10075):
 *       _BIX -> BTIX (Zero): _BIX[1]=1 (mAh), _BIX[2]=BDC, _BIX[3]=BFC (or 80% BDC if MXCG==0x50)
 *       _BST -> BTST (Zero): AML 140C5F42535400A44254535400 at 0xDC51 (unique match, Count=1)
 *       _BST[2] = BRC (Remaining Capacity in mAh, same Power Unit as _BIX[3])
 *   - \_SB.BAT1 (DSDT.dsl:10142, _STA=0):
 *       _BST -> BTST (One): AML 140C5F42535400A44254535401 at 0xDCB6 (untouched by patch)
 *
 * Companion OpenCore ACPI Patch (TableSignature=DSDT, Count=1):
 *   Find:    140C5F42535400A44254535400 (FAxfQlNUAKRCVFNUAA==)
 *   Replace: 140C5842535400A44254535400 (FAxYQlNUAKRCVFNUAA==)
 *
 * Safety:
 *   - Renames only \_SB.BAT0._BST -> XBST (leaving \_SB.BAT1._BST intact).
 *   - Non-Darwin OSes return XBST () unmodified.
 *   - Avoids all direct 16-bit EC FieldUnit reads: delegates to XBST (), _BIX (),
 *     and \_SB.PC00.LPCB.EC0.GACS () (1-bit ADP / 8-bit ACIX / RAM ACST).
 *   - Under Darwin, when AC is online (GACS () != Zero), battery is neither
 *     charging nor discharging ((state & 0x03) == Zero), capacities are valid
 *     (> 0 and < 0x7FFFFFFF), Remaining < LastFull, and Remaining >= 97% of
 *     LastFull ((Remaining * 100) >= (LastFull * 97)), clamps Remaining to
 *     LastFull in a dedicated FBST package.
 */
DefinitionBlock ("", "SSDT", 2, "HPS0IX", "BATFULL", 0x00001000)
{
    External (\_SB.BAT0, DeviceObj)
    External (\_SB.BAT0.XBST, MethodObj)    // 0 Arguments
    External (\_SB.BAT0._BIX, MethodObj)    // 0 Arguments
    External (\_SB.PC00.LPCB.EC0.GACS, MethodObj)    // 0 Arguments

    Scope (\_SB.BAT0)
    {
        Name (FBST, Package (0x04)
        {
            Zero,
            Zero,
            Zero,
            Zero
        })

        Method (_BST, 0, Serialized)  // _BST: Battery Status
        {
            Local0 = XBST ()
            If (!_OSI ("Darwin"))
            {
                Return (Local0)
            }

            If ((\_SB.PC00.LPCB.EC0.GACS () == Zero))
            {
                Return (Local0)
            }

            Local1 = DerefOf (Local0 [Zero])        // Battery State
            If ((Local1 & 0x03))                    // Discharging (0x01) or Charging (0x02)
            {
                Return (Local0)
            }

            Local2 = DerefOf (Local0 [0x02])        // Remaining Capacity (mAh)
            Local3 = _BIX ()
            Local4 = DerefOf (Local3 [0x03])        // Last Full Charge Capacity (mAh)
            If (((Local2 == Zero) || (Local2 >= 0x7FFFFFFF) ||
                 (Local4 == Zero) || (Local4 >= 0x7FFFFFFF) ||
                 (Local2 >= Local4)))
            {
                Return (Local0)
            }

            // Within 3% of Last Full Charge Capacity (>= 97%): report full.
            If (((Local2 * 0x64) >= (Local4 * 0x61)))
            {
                FBST [Zero] = Local1
                FBST [One] = DerefOf (Local0 [One])
                FBST [0x02] = Local4
                FBST [0x03] = DerefOf (Local0 [0x03])
                Return (FBST)
            }

            Return (Local0)
        }
    }
}
