# Independent A2/A3 proof pack

Full report: [null-stencil and draw semantics](../track-a/reports/stencil-and-draw-semantics.md).

* [Stencil proof](../track-a/stencil-proof.json): actual ICL disabled5DW command
  and companion Depth/HiZ/WM state; TGL8DW `SURFTYPE_NULL` reconstruction.
* [Draw proof](../track-a/draw-proof.json): malformed source under both PRMs;
  valid A=`7b000808` and B=`7b000005`+3NOOP, with explicit XP/VF conditions.
* [Provenance](../reference/track-a/provenance.json): six present PDF hashes,
  official URLs, later byte-identical official PDF revalidation, exact Mesa
  commit/source comparison and executed independent generated-pack check.

Concrete stencil example is `78060006 e0000000 0 0 0 4 0 0`, conditional on
target-validated MOCS4 and explicitly absent/disabled resources. MOCS0 is not
accepted by the fixed Mesa gen12 pack constraint. Runtime MOCS is unresolved.
No equivalence to malformed-source execution or GPU readiness is asserted.
