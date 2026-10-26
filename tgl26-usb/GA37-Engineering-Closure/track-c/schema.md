# GA37 Track C schema index

`FAULTRECORD-V2.md` is the normative offset table.  This index records the
wire invariants used by the strict decoder:

* magic: bytes `54 47 46 34` (`TGF4`); version: little-endian `02 00`;
* fixed length: little-endian `80 01 00 00` at offset 8 (384 bytes);
* all multi-byte values are explicit little-endian, never native struct dumps;
* 64-bit values begin at 8-byte-aligned offsets;
* reserved ranges are `[60,64)`, `[132,136)`, `[164,168)`, `[204,208)`,
  `[280,288)`, and `[360,384)` and must be all zero;
* presence/unknown masks cover only field bits 0..21;
* status arrays contain only 0=`UNKNOWN`, 1=`CONDITIONAL`, 2=`PASS`,
  3=`FAILED`;
* raw DWORDs are offsets 120, 124, 128; derived VA is offset 168 and is not
  read back as raw data;
* context identity, PML4, ring head, engine, allocation generation, and
  provenance are optional claims.  No validator derives or invents them;
* v1 is a separate exact 108-byte format and is not widened in place.
