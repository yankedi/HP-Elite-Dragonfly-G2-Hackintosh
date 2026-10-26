/*
 * Source-level NMX personality checks.
 *
 * This is deliberately not an IORegistry or GPU implementation.  It only
 * classifies the PCI identity already carried by a drmDevice and compares
 * PCI bus identities.  A future NMXGPU provider can consume these checks
 * without this shim inventing registry topology or execution capability.
 */
#ifndef GA41_NMX_IDENTITY_H
#define GA41_NMX_IDENTITY_H

#include <xf86drm.h>

#ifdef __cplusplus
extern "C" {
#endif

enum nmx_personality {
   NMX_PERSONALITY_UNKNOWN = 0,
   NMX_PERSONALITY_INTEL,
   NMX_PERSONALITY_AMD,
};

enum nmx_personality nmx_pci_personality(const drmDevicePtr device);
int nmx_pci_identity_equal(const drmDevicePtr a, const drmDevicePtr b);
const char *nmx_personality_name(enum nmx_personality personality);

#ifdef __cplusplus
}
#endif

#endif /* GA41_NMX_IDENTITY_H */
