//
//  kern_igfx.cpp
//  WhateverGreen
//
//  Copyright © 2018 vit9696. All rights reserved.
//

#include <Headers/kern_nvram.hpp>
#include "kern_igfx.hpp"
#include "kern_fb.hpp"
#include "kern_guc.hpp"
#include "kern_agdc.hpp"
#include "kern_igfx_kexts.hpp"

#include <Headers/kern_api.hpp>
#include <Headers/kern_cpu.hpp>
#include <Headers/kern_file.hpp>
#include <Headers/kern_iokit.hpp>

#include <IOKit/pci/IOPCIDevice.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOMemoryDescriptor.h>
#include <sys/vnode.h>
#include <sys/uio.h>
#include <sys/fcntl.h>
#include <sys/errno.h>

IGFX *IGFX::callbackIGFX;

void IGFX::init() {
	callbackIGFX = this;
	// Initialize each submodule
	for (auto submodule : submodules)
		submodule->init();
	for (auto submodule : sharedSubmodules)
		submodule->init();
	auto &bdi = BaseDeviceInfo::get();
	auto generation = bdi.cpuGeneration;
	auto family = bdi.cpuFamily;
	auto model = bdi.cpuModel;
	switch (generation) {
		case CPUInfo::CpuGeneration::Penryn:
		case CPUInfo::CpuGeneration::Nehalem:
			// Do not warn about legacy processors (e.g. Xeon).
			break;
		case CPUInfo::CpuGeneration::Westmere:
			currentGraphics = &kextIntelHD;
			currentFramebuffer = &kextIntelHDFb;
			break;
		case CPUInfo::CpuGeneration::SandyBridge: {
			int tmp = 1;
			PE_parse_boot_argn("igfxsnb", &tmp, sizeof(tmp));
			moderniseAccelerator = tmp == 1;
			currentGraphics = &kextIntelHD3000;
			currentFramebuffer = &kextIntelSNBFb;
			break;
		}
		case CPUInfo::CpuGeneration::IvyBridge:
			currentGraphics = &kextIntelHD4000;
			currentFramebuffer = &kextIntelCapriFb;
			break;
		case CPUInfo::CpuGeneration::Haswell:
			currentGraphics = &kextIntelHD5000;
			currentFramebuffer = &kextIntelAzulFb;
			break;
		case CPUInfo::CpuGeneration::Broadwell:
			currentGraphics = &kextIntelBDW;
			currentFramebuffer = &kextIntelBDWFb;
			break;
		case CPUInfo::CpuGeneration::Skylake:
			// Fake SKL as KBL on 13.0+ due to the removal of SKL kexts
			// Or KBL kext can be used on SKL with older versions as well with KBL `device-id' and `ig-platform-id' injected.
			forceSKLAsKBL = getKernelVersion() >= KernelVersion::Ventura || checkKernelArgument("-igfxsklaskbl");
			if (forceSKLAsKBL) {
				DBGLOG("igfx", "enforcing KBL kexts and patches on Skylake");
				supportsGuCFirmware = true;
				currentGraphics = &kextIntelKBL;
				currentFramebuffer = &kextIntelKBLFb;
				modForceCompleteModeset.supported = modForceCompleteModeset.enabled = true;
				modRPSControlPatch.available = true;
				modForceWakeWorkaround.enabled = true;
				modTypeCCheckDisabler.enabled = getKernelVersion() >= KernelVersion::BigSur;
				modBlackScreenFix.available = true;
			} else {
				supportsGuCFirmware = true;
				currentGraphics = &kextIntelSKL;
				currentFramebuffer = &kextIntelSKLFb;
				modForceCompleteModeset.supported = modForceCompleteModeset.legacy = true; // not enabled, as on legacy operating systems it casues crashes.
				modTypeCCheckDisabler.enabled = getKernelVersion() >= KernelVersion::BigSur;
				modBlackScreenFix.available = true;
			}
			break;
		case CPUInfo::CpuGeneration::KabyLake:
			supportsGuCFirmware = true;
			currentGraphics = &kextIntelKBL;
			currentFramebuffer = &kextIntelKBLFb;
			modForceCompleteModeset.supported = modForceCompleteModeset.enabled = true;
			modRPSControlPatch.available = true;
			modForceWakeWorkaround.enabled = true;
			modTypeCCheckDisabler.enabled = getKernelVersion() >= KernelVersion::BigSur;
			modBlackScreenFix.available = true;
			break;
		case CPUInfo::CpuGeneration::CoffeeLake:
			supportsGuCFirmware = true;
			currentGraphics = &kextIntelKBL;
			currentFramebuffer = &kextIntelCFLFb;
			// Allow faking ask KBL
			currentFramebufferOpt = &kextIntelKBLFb;
			// Note, several CFL GPUs are completely broken. They freeze in IGMemoryManager::initCache due to incompatible
			// configuration, supposedly due to Apple not supporting new MOCS table and forcing Skylake-based format.
			// See: https://github.com/torvalds/linux/blob/135c5504a600ff9b06e321694fbcac78a9530cd4/drivers/gpu/drm/i915/intel_mocs.c#L181
			modForceCompleteModeset.supported = modForceCompleteModeset.enabled = true;
			modRPSControlPatch.available = true;
			modForceWakeWorkaround.enabled = true;
			modTypeCCheckDisabler.enabled = true;
			modBlackScreenFix.available = true;
			break;
		case CPUInfo::CpuGeneration::CannonLake:
			supportsGuCFirmware = true;
			currentGraphics = &kextIntelCNL;
			currentFramebuffer = &kextIntelCNLFb;
			modForceCompleteModeset.supported = modForceCompleteModeset.enabled = true;
			modTypeCCheckDisabler.enabled = true;
			break;
		case CPUInfo::CpuGeneration::IceLake:
			supportsGuCFirmware = true;
			currentGraphics = &kextIntelICL;
			currentFramebuffer = &kextIntelICLLPFb;
			currentFramebufferOpt = &kextIntelICLHPFb;
			modDVMTCalcFix.available = true;
			break;
		case CPUInfo::CpuGeneration::CometLake:
			supportsGuCFirmware = true;
			currentGraphics = &kextIntelKBL;
			currentFramebuffer = &kextIntelCFLFb;
			// Allow faking ask KBL
			currentFramebufferOpt = &kextIntelKBLFb;
			// Note, several CFL GPUs are completely broken. They freeze in IGMemoryManager::initCache due to incompatible
			// configuration, supposedly due to Apple not supporting new MOCS table and forcing Skylake-based format.
			// See: https://github.com/torvalds/linux/blob/135c5504a600ff9b06e321694fbcac78a9530cd4/drivers/gpu/drm/i915/intel_mocs.c#L181
			modForceCompleteModeset.supported = modForceCompleteModeset.enabled = true;
			modRPSControlPatch.available = true;
			modTypeCCheckDisabler.enabled = true;
			modBlackScreenFix.available = true;
			break;
		case CPUInfo::CpuGeneration::TigerLake:
			// Experimental and opt-in. There is no Tiger Lake driver; route the ICL LP framebuffer so that
			// framebuffer patches and the MMIO tracer can act on it. The accelerator is deliberately left alone.
			if (checkKernelArgument("-igfxtgl"))
				currentFramebuffer = &kextIntelICLLPFb;
			else
				SYSLOG("igfx", "found an unsupported processor 0x%X:0x%X, please report this!", family, model);
			break;
		case CPUInfo::CpuGeneration::RocketLake:
		case CPUInfo::CpuGeneration::AlderLake:
		case CPUInfo::CpuGeneration::RaptorLake:
		case CPUInfo::CpuGeneration::ArrowLake:
			gPlatformGraphicsSupported = false;
			break;
		default:
			SYSLOG("igfx", "found an unsupported processor 0x%X:0x%X, please report this!", family, model);
			break;
	}

	if (currentGraphics)
		lilu.onKextLoadForce(currentGraphics);

	if (currentFramebuffer)
		lilu.onKextLoadForce(currentFramebuffer);

	if (currentFramebufferOpt)
		lilu.onKextLoadForce(currentFramebufferOpt);
}

void IGFX::deinit() {
	// Deinitialize each submodule
	for (auto submodule : submodules)
		submodule->deinit();
	for (auto submodule : sharedSubmodules)
		submodule->deinit();
}

void IGFX::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	bool switchOffGraphics = false;
	bool switchOffFramebuffer = false;
	framebufferPatch.framebufferId = info->reportedFramebufferId;

	auto cpuGeneration = BaseDeviceInfo::get().cpuGeneration;

	if (info->videoBuiltin && !gPlatformGraphicsSupported) {
		switchOffGraphics = switchOffFramebuffer = true;
	} else if (info->videoBuiltin) {
		applyFramebufferPatch = loadPatchesFromDevice(info->videoBuiltin, info->reportedFramebufferId);

#ifdef DEBUG
		dumpFramebufferToDisk = checkKernelArgument("-igfxdump");
		dumpPlatformTable = checkKernelArgument("-igfxfbdump");
#endif

		if (supportsGuCFirmware && getKernelVersion() >= KernelVersion::HighSierra) {
			if (!PE_parse_boot_argn("igfxfw", &fwLoadMode, sizeof(fwLoadMode)))
				WIOKit::getOSDataValue<int32_t>(info->videoBuiltin, "igfxfw", fwLoadMode);
			if (fwLoadMode == FW_AUTO)
				fwLoadMode = info->firmwareVendor == DeviceInfo::FirmwareVendor::Apple ? FW_APPLE : FW_DISABLE;
		} else {
			fwLoadMode = FW_APPLE; /* Do nothing, GuC is either unsupported due to low OS or Apple */
		}
		
		disableAccel = checkKernelArgument("-igfxvesa");

		disableIGTelemetry = info->videoBuiltin->getProperty("disable-telemetry-load") != nullptr || checkKernelArgument("-igfxnotelemetryload");

		bool connectorLessFrame = info->reportedFramebufferIsConnectorLess;

		int gl = info->videoBuiltin->getProperty("disable-metal") != nullptr;
		PE_parse_boot_argn("igfxgl", &gl, sizeof(gl));
		forceOpenGL = gl == 1;

		int metal = info->videoBuiltin->getProperty("enable-metal") != nullptr;
		PE_parse_boot_argn("igfxmetal", &metal, sizeof(metal));
		forceMetal = metal == 1;

		// Automatically enable HDMI -> DP patches
		bool nohdmi = info->videoBuiltin->getProperty("disable-hdmi-patches") != nullptr;
		hdmiAutopatch = !applyFramebufferPatch && !connectorLessFrame && getKernelVersion() >= Yosemite &&
			cpuGeneration >= CPUInfo::CpuGeneration::SandyBridge && !checkKernelArgument("-igfxnohdmi") && !nohdmi;
		
		// Set AAPL00,DualLink to zero on Westmere if applying single link patches.
		if (cpuGeneration == CPUInfo::CpuGeneration::Westmere && framebufferWestmerePatches.SingleLink) {
			uint8_t dualLinkBytes[] { 0x00, 0x00, 0x00, 0x00 };
			info->videoBuiltin->setProperty("AAPL00,DualLink", dualLinkBytes, sizeof(dualLinkBytes));
		}
		
		// Note that the order does matter
		// We first iterate through each submodule and redirect the request
		for (auto submodule : submodules)
			submodule->processKernel(patcher, info);
		
		// Then process shared submodules
		// A shared submodule will disable itself if no active submodule depends on it
		for (auto submodule : sharedSubmodules)
			submodule->processKernel(patcher, info);
		
		// Iterate through each submodule and see if we need to patch the graphics and the framebuffer kext
		auto submodulesRequiresFramebufferPatch = false;
		auto submodulesRequiresGraphicsPatch = false;
		for (auto submodule : submodules) {
			submodulesRequiresFramebufferPatch |= submodule->requiresPatchingFramebuffer;
			submodulesRequiresGraphicsPatch |= submodule->requiresPatchingGraphics;
		}
		
		// Ideally, we could get rid of these two lambda expressions
		auto requiresFramebufferPatches = [this]() {
			if (applyFramebufferPatch || hdmiAutopatch)
				return true;
			if (dumpFramebufferToDisk || dumpPlatformTable)
				return true;
			return false;
		};

		auto requiresGraphicsPatches = [this]() {
			if (forceOpenGL)
				return true;
			if (forceMetal)
				return true;
			if (moderniseAccelerator)
				return true;
			if (fwLoadMode != FW_APPLE)
				return true;
			if (disableAccel)
				return true;
			if (disableIGTelemetry)
				return true;
			return false;
		};

		// Disable kext patching if we have nothing to do.
		switchOffFramebuffer = !requiresFramebufferPatches() && !submodulesRequiresFramebufferPatch;
		switchOffGraphics = !requiresGraphicsPatches() && !submodulesRequiresGraphicsPatch;
	} else {
		switchOffGraphics = switchOffFramebuffer = true;
	}

	if (switchOffGraphics && currentGraphics)
		currentGraphics->switchOff();

	if (switchOffFramebuffer) {
		if (currentFramebuffer)
			currentFramebuffer->switchOff();
		if (currentFramebufferOpt)
			currentFramebufferOpt->switchOff();
	}

	if (moderniseAccelerator) {
		KernelPatcher::RouteRequest request("__ZN9IOService20copyExistingServicesEP12OSDictionaryjj", wrapCopyExistingServices, orgCopyExistingServices);
		patcher.routeMultiple(KernelPatcher::KernelID, &request, 1);
	}
}

bool IGFX::processKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	auto cpuGeneration = BaseDeviceInfo::get().cpuGeneration;

	if (currentGraphics && currentGraphics->loadIndex == index) {
		if (disableIGTelemetry) {
			auto symTelemetry = patcher.solveSymbol(index, "__ZN18IGTelemetryManager16prepareTelemetryEj");
			if (symTelemetry) {
				uint8_t ret[] {0xC3};
				patcher.routeBlock(symTelemetry, ret, sizeof(ret));
				if (patcher.getError() == KernelPatcher::Error::NoError) {
					DBGLOG("igfx", "disabled __ZN18IGTelemetryManager16prepareTelemetryEj");
				} else {
					SYSLOG("igfx", "failed to disable __ZN18IGTelemetryManager16prepareTelemetryEj with code %d", patcher.getError());
					patcher.clearError();
				}
			} else {
				SYSLOG("igfx", "failed to resolve __ZN18IGTelemetryManager16prepareTelemetryE code %d", patcher.getError());
				patcher.clearError();
			}
		}

		if (forceOpenGL || forceMetal || forceSKLAsKBL || moderniseAccelerator || fwLoadMode != FW_APPLE || disableAccel) {
			KernelPatcher::RouteRequest request("__ZN16IntelAccelerator5startEP9IOService", wrapAcceleratorStart, orgAcceleratorStart);
			patcher.routeMultiple(index, &request, 1, address, size);

			if (fwLoadMode == FW_GENERIC && getKernelVersion() <= KernelVersion::Mojave)
				loadIGScheduler4Patches(patcher, index, address, size);
		}
		
		// Note that the order is reversed at this stage
		// We first process shared submodules
		// If a shared submodule fails to process the acceleration driver,
		// all subdmoules that depend on it will be disabled automatically.
		for (auto submodule : sharedSubmodules)
			if (submodule->enabled)
				submodule->processGraphicsKext(patcher, index, address, size);
		
		// Then iterate through each submodule and redirect the request if and only if it is enabled
		for (auto submodule : submodules)
			if (submodule->enabled)
				submodule->processGraphicsKext(patcher, index, address, size);

		return true;
	}

	if ((currentFramebuffer && currentFramebuffer->loadIndex == index) ||
		(currentFramebufferOpt && currentFramebufferOpt->loadIndex == index)) {
		
		// Note that the order is reversed at this stage
		// We first process shared submodules
		// If a shared submodule fails to process the framebuffer driver,
		// all subdmoules that depend on it will be disabled automatically.
		for (auto submodule : sharedSubmodules)
			if (submodule->enabled)
				submodule->processFramebufferKext(patcher, index, address, size);
		
		// Then iterate through each submodule and redirect the request if and only if it is enabled
		for (auto submodule : submodules)
			if (submodule->enabled)
				submodule->processFramebufferKext(patcher, index, address, size);

		if (applyFramebufferPatch || dumpFramebufferToDisk || dumpPlatformTable || hdmiAutopatch) {
			framebufferStart = reinterpret_cast<uint8_t *>(address);
			framebufferSize = size;
			
			if (cpuGeneration >= CPUInfo::CpuGeneration::SandyBridge) {
				if (cpuGeneration == CPUInfo::CpuGeneration::SandyBridge) {
					gPlatformListIsSNB = true;
					gPlatformInformationList = patcher.solveSymbol<void *>(index, "_PlatformInformationList", address, size);
				} else {
					gPlatformListIsSNB = false;
					gPlatformInformationList = patcher.solveSymbol<void *>(index, "_gPlatformInformationList", address, size);
				}

				DBGLOG("igfx", "platform is snb %d and list " PRIKADDR, gPlatformListIsSNB, CASTKADDR(gPlatformInformationList));
			}

			if ((gPlatformInformationList && cpuGeneration >= CPUInfo::CpuGeneration::SandyBridge) || cpuGeneration == CPUInfo::CpuGeneration::Westmere) {
				auto fbGetOSInformation = "__ZN31AppleIntelFramebufferController16getOSInformationEv";
				if (cpuGeneration == CPUInfo::CpuGeneration::Westmere)
					fbGetOSInformation = "__ZN22AppleIntelHDGraphicsFB16getOSInformationEv";
				else if (cpuGeneration == CPUInfo::CpuGeneration::SandyBridge)
					fbGetOSInformation = "__ZN23AppleIntelSNBGraphicsFB16getOSInformationEv";
				else if (cpuGeneration == CPUInfo::CpuGeneration::IvyBridge)
					fbGetOSInformation = "__ZN25AppleIntelCapriController16getOSInformationEv";
				else if (cpuGeneration == CPUInfo::CpuGeneration::Haswell)
					fbGetOSInformation = "__ZN24AppleIntelAzulController16getOSInformationEv";
				else if (cpuGeneration == CPUInfo::CpuGeneration::Broadwell)
					fbGetOSInformation = "__ZN22AppleIntelFBController16getOSInformationEv";

				KernelPatcher::RouteRequest request(fbGetOSInformation, wrapGetOSInformation, orgGetOSInformation);
				patcher.routeMultiple(index, &request, 1, address, size);
			} else if (cpuGeneration >= CPUInfo::CpuGeneration::SandyBridge) {
				SYSLOG("igfx", "failed to obtain gPlatformInformationList pointer with code %d", patcher.getError());
				patcher.clearError();
			}
			
			if (applyFramebufferPatch && cpuGeneration == CPUInfo::CpuGeneration::Westmere) {
				KernelPatcher::RouteRequest requestWestmere("__ZN22AppleIntelHDGraphicsFB8TrainFDIEiPNS_10CRTCParamsE", wrapTrainFDI, orgTrainFDI);
				patcher.routeMultiple(index, &requestWestmere, 1, address, size);
				
				applyWestmerePatches(patcher);
			}
		}
		return true;
	}

	return false;
}

// MARK: - Global Framebuffer Controller Access Support

void IGFX::FramebufferControllerAccessSupport::init() {
	// We only need to patch the framebuffer driver
	requiresPatchingFramebuffer = true;
}

void IGFX::FramebufferControllerAccessSupport::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	// Enable if at least one active submodule relies on this shared module
	for (auto submodule : callbackIGFX->submodules)
		if (submodule->enabled)
			enabled |= submodule->requiresGlobalFramebufferControllersAccess;
	
	DBGLOG("igfx", "FCA: Enabled = %d.", enabled);
}

void IGFX::FramebufferControllerAccessSupport::processFramebufferKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	KernelPatcher::SolveRequest request("_gController", controllers);
	if (!patcher.solveMultiple(index, &request, 1, address, size)) {
		SYSLOG("igfx", "FCA: Failed to resolve the symbol of global controllers. Will disable all submodules that rely on this one.");
		disableDependentSubmodules();
	}
}

void IGFX::FramebufferControllerAccessSupport::disableDependentSubmodules() {
	for (auto submodule : callbackIGFX->submodules)
		if (submodule->requiresGlobalFramebufferControllersAccess)
			submodule->enabled = false;
}

// MARK: - MMIO Registers Read Support

void IGFX::MMIORegistersReadSupport::init() {
	// We only need to patch the framebuffer driver
	requiresPatchingFramebuffer = true;
}

void IGFX::MMIORegistersReadSupport::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	// Enable the verbose output if the boot argument is found
	verbose = checkKernelArgument("-igfxvamregs");
	enabled |= verbose;
	
	// Enable if at least one active submodule relies on this shared module
	for (auto submodule : callbackIGFX->submodules)
		if (submodule->enabled)
			enabled |= submodule->requiresMMIORegistersReadAccess;
	
	DBGLOG("igfx", "RRS: Enabled = %d.", enabled);
}

void IGFX::MMIORegistersReadSupport::processFramebufferKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	// Symbol Table:
	// IVB*: "__ZN25AppleIntelCapriController14ReadRegister32Em"
	// HSW*: "__ZN24AppleIntelAzulController14ReadRegister32Em"
	// BDW*: "__ZNK22AppleIntelFBController14ReadRegister32Em"
	// SKL+: "__ZN31AppleIntelFramebufferController14ReadRegister32Em"
	const char* symbol = nullptr;
	
	auto framebuffer = Value::of(callbackIGFX->getRealFramebuffer(index));
	if (framebuffer.isOneOf(&kextIntelCapriFb)) {
		symbol = "__ZN25AppleIntelCapriController14ReadRegister32Em";
		DBGLOG("igfx", "RRS: Will setup the read register module for IVB platform.");
	} else if (framebuffer.isOneOf(&kextIntelAzulFb)) {
		symbol = "__ZN24AppleIntelAzulController14ReadRegister32Em";
		DBGLOG("igfx", "RRS: Will setup the read register module for HSW platform.");
	} else if (framebuffer.isOneOf(&kextIntelBDWFb)) {
		symbol = "__ZNK22AppleIntelFBController14ReadRegister32Em";
		DBGLOG("igfx", "RRS: Will setup the read register module for BDW platform.");
	} else if (framebuffer.isOneOf(&kextIntelSKLFb, &kextIntelKBLFb, &kextIntelCFLFb, &kextIntelICLLPFb)) {
		symbol = "__ZN31AppleIntelFramebufferController14ReadRegister32Em";
		DBGLOG("igfx", "RRS: Will setup the read register module for SKL/KBL/CFL/ICL platform.");
	} else {
		SYSLOG("igfx", "RRS: Found an unsupported platform. Will disable all submodules that depend on RRS.");
		return disableDependentSubmodules();
	}
	
	KernelPatcher::RouteRequest request(symbol, wrapReadRegister32, orgReadRegister32);
	if (!patcher.routeMultiple(index, &request, 1, address, size)) {
		SYSLOG("igfx", "RRS: Failed to resolve the symbol of ReadRegister32. Will disable all submodules that rely on this one.");
		disableDependentSubmodules();
	}
}

void IGFX::MMIORegistersReadSupport::disableDependentSubmodules() {
	for (auto submodule : callbackIGFX->submodules)
		if (submodule->requiresMMIORegistersReadAccess)
			submodule->enabled = false;
}

uint32_t IGFX::MMIORegistersReadSupport::wrapReadRegister32(void *controller, uint32_t address) {
	// Guard: Perform prologue injections
	auto prologueInjector = callbackIGFX->modMMIORegistersReadSupport.prologueList.getInjector(address);
	if (prologueInjector) {
		DBGLOG("igfx", "RRS: Found a prologue injector triggered by the register address 0x%x.", address);
		prologueInjector(controller, address);
	}
	
	// Guard: Perform replacer injections
	auto replacerInjector = callbackIGFX->modMMIORegistersReadSupport.replacerList.getInjector(address);
	if (replacerInjector) {
		DBGLOG("igfx", "RRS: Found a replacer injector triggered by the register value 0x%x.", address);
		return replacerInjector(controller, address);
	}
	
	// Invoke the original function
	auto &tracer = callbackIGFX->modTigerLakeTracer;
	size_t slot = tracer.enabled ? tracer.onAccess(false, address, 0) : 0;
	auto &regMap = callbackIGFX->modTigerLakeRegisterMap;
	uint32_t retVal = regMap.enabled ? regMap.read(controller, address) : callbackIGFX->modMMIORegistersReadSupport.orgReadRegister32(controller, address);
	if (tracer.enabled)
		tracer.ring[slot].value = retVal;
	if (callbackIGFX->modMMIORegistersReadSupport.verbose)
		DBGLOG("igfx", "RRS: Read MMIO Register = 0x%x; Value = 0x%x.", address, retVal);
	
	// Guard: Perform epilogue injections
	auto epilogueInjector = callbackIGFX->modMMIORegistersReadSupport.epilogueList.getInjector(address);
	if (epilogueInjector) {
		DBGLOG("igfx", "RRS: Found a epilogue injector triggered by the register value 0x%x.", address);
		return epilogueInjector(controller, address, retVal);
	}
	
	// Return the register value retrieved from the original function
	return retVal;
}

// MARK: - MMIO Registers Write Support

void IGFX::MMIORegistersWriteSupport::init() {
	// We only need to patch the framebuffer driver
	requiresPatchingFramebuffer = true;
}

void IGFX::MMIORegistersWriteSupport::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	// Enable the verbose output if the boot argument is found
	verbose = checkKernelArgument("-igfxvamregs");
	enabled |= verbose;
	
	// Enable if at least one active submodule relies on this shared module
	for (auto submodule : callbackIGFX->submodules)
		if (submodule->enabled)
			enabled |= submodule->requiresMMIORegistersWriteAccess;
	
	DBGLOG("igfx", "RWS: Enabled = %d.", enabled);
}

void IGFX::MMIORegistersWriteSupport::processFramebufferKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	// Symbol Table:
	// IVB*: "__ZN25AppleIntelCapriController15WriteRegister32Emj"
	// HSW*: "__ZN24AppleIntelAzulController15WriteRegister32Emj"
	// BDW*: "__ZN22AppleIntelFBController15WriteRegister32Emj"
	// SKL+: "__ZN31AppleIntelFramebufferController15WriteRegister32Emj"
	const char* symbol = nullptr;
	
	auto framebuffer = Value::of(callbackIGFX->getRealFramebuffer(index));
	if (framebuffer.isOneOf(&kextIntelCapriFb)) {
		symbol = "__ZN25AppleIntelCapriController15WriteRegister32Emj";
		DBGLOG("igfx", "RWS: Will setup the read register module for IVB platform.");
	} else if (framebuffer.isOneOf(&kextIntelAzulFb)) {
		symbol = "__ZN24AppleIntelAzulController15WriteRegister32Emj";
		DBGLOG("igfx", "RWS: Will setup the read register module for HSW platform.");
	} else if (framebuffer.isOneOf(&kextIntelBDWFb)) {
		symbol = "__ZN22AppleIntelFBController15WriteRegister32Emj";
		DBGLOG("igfx", "RWS: Will setup the read register module for BDW platform.");
	} else if (framebuffer.isOneOf(&kextIntelSKLFb, &kextIntelKBLFb, &kextIntelCFLFb, &kextIntelICLLPFb)) {
		symbol = "__ZN31AppleIntelFramebufferController15WriteRegister32Emj";
		DBGLOG("igfx", "RWS: Will setup the read register module for SKL/KBL/CFL/ICL platform.");
	} else {
		SYSLOG("igfx", "RWS: Found an unsupported platform. Will disable all submodules that depend on RWS.");
		return disableDependentSubmodules();
	}
	
	KernelPatcher::RouteRequest request(symbol, wrapWriteRegister32, orgWriteRegister32);
	if (!patcher.routeMultiple(index, &request, 1, address, size)) {
		SYSLOG("igfx", "RWS: Failed to resolve the symbol of WriteRegister32. Will disable all submodules that rely on this one.");
		disableDependentSubmodules();
	}
}

void IGFX::MMIORegistersWriteSupport::disableDependentSubmodules() {
	for (auto submodule : callbackIGFX->submodules)
		if (submodule->requiresMMIORegistersWriteAccess)
			submodule->enabled = false;
}

void IGFX::MMIORegistersWriteSupport::wrapWriteRegister32(void *controller, uint32_t address, uint32_t value) {
	// Guard: Perform prologue injections
	auto prologueInjector = callbackIGFX->modMMIORegistersWriteSupport.prologueList.getInjector(address);
	if (prologueInjector) {
		DBGLOG("igfx", "RWS: Found a prologue injector triggered by the register address 0x%x.", address);
		prologueInjector(controller, address, value);
	}
	
	// Guard: Perform replacer injections
	auto replacerInjector = callbackIGFX->modMMIORegistersWriteSupport.replacerList.getInjector(address);
	if (replacerInjector) {
		DBGLOG("igfx", "RWS: Found a replacer injector triggered by the register value 0x%x.", address);
		return replacerInjector(controller, address, value);
	}
	
	// Invoke the original function
	if (callbackIGFX->modTigerLakeTracer.enabled)
		callbackIGFX->modTigerLakeTracer.onAccess(true, address, value);
	if (callbackIGFX->modTigerLakeRegisterMap.enabled)
		callbackIGFX->modTigerLakeRegisterMap.write(controller, address, value);
	else
		callbackIGFX->modMMIORegistersWriteSupport.orgWriteRegister32(controller, address, value);
	if (callbackIGFX->modMMIORegistersWriteSupport.verbose)
		DBGLOG("igfx", "RWS: Write MMIO Register = 0x%x; Value = 0x%x.", address, value);
	
	// Guard: Perform epilogue injections
	auto epilogueInjector = callbackIGFX->modMMIORegistersWriteSupport.epilogueList.getInjector(address);
	if (epilogueInjector) {
		DBGLOG("igfx", "RWS: Found a epilogue injector triggered by the register value 0x%x.", address);
		return epilogueInjector(controller, address, value);
	}
}

// MARK: - Tiger Lake MMIO Tracer

void IGFX::TigerLakeTracer::init() {
	// We rely on the shared MMIO read and write support to see every register access
	requiresPatchingFramebuffer = true;
	requiresMMIORegistersReadAccess = true;
	requiresMMIORegistersWriteAccess = true;
}

void IGFX::TigerLakeTracer::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	enabled = BaseDeviceInfo::get().cpuGeneration == CPUInfo::CpuGeneration::TigerLake && checkKernelArgument("-igfxtgl");
	if (!enabled)
		return;

	PE_parse_boot_argn("igfxtglstop", &stopAt, sizeof(stopAt));
	park = checkKernelArgument("-igfxtglpark");
	SYSLOG("igfx", "TGL: Tracing framebuffer MMIO. Will stop before access %u by %s.", stopAt, park ? "parking" : "panicking");
}

size_t IGFX::TigerLakeTracer::onAccess(bool write, uint32_t address, uint32_t value) {
	auto index = static_cast<uint32_t>(OSIncrementAtomic(&count)) + 1;
	size_t slot = index % RingSize;
	ring[slot] = {index, address, value, write};
	if (index != stopAt)
		return slot;

	// The chosen access is never performed. Report the history, oldest first, then stop here.
	static char report[RingSize * 40 + 96];
	size_t len = snprintf(report, sizeof(report), "igfx TGL: stopped before access %u (%s 0x%05X)\n", index, write ? "W" : "R", address);
	for (size_t i = 1; i < RingSize && len < sizeof(report); i++) {
		auto &access = ring[(index + i) % RingSize];
		if (access.index == 0)
			continue;
		if (park)
			SYSLOG("igfx", "TGL: %u %s 0x%05X = 0x%08X", access.index, access.write ? "W" : "R", access.address, access.value);
		len += snprintf(report + len, sizeof(report) - len, "%u %s 0x%05X = 0x%08X\n", access.index, access.write ? "W" : "R", access.address, access.value);
	}

	if (park) {
		SYSLOG("igfx", "TGL: Stopped before access %u (%s 0x%05X). Parking this thread.", index, write ? "W" : "R", address);
		while (true)
			IOSleep(1000);
	}

	PANIC("igfx", "%s", report);
}

// MARK: - Tiger Lake Function Tracer

// Audited against AppleIntelICLLPGraphicsFramebuffer from macOS 26.6 (25G72), see results/analysis/SYMBOLS.md.
// safeLength is the number of leading bytes with no relative operands; a trampoline may only copy those.
const IGFX::TigerLakeFunctionTracer::Function IGFX::TigerLakeFunctionTracer::functions[] {
	{"__ZN31AppleIntelFramebufferController5startEP9IOService", "AIFC::start", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x55, 0x41, 0x54, 0x53, 0x48, 0x83, 0xEC}, 23},
	{"__ZN31AppleIntelFramebufferController20initInterruptServiceEv", "AIFC::initInterruptService", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x55, 0x41, 0x54, 0x53, 0x50, 0x48, 0x89}, 35},
	{"__Z14registerSysctlv", "registerSysctl", {0x55, 0x48, 0x89, 0xE5, 0x31, 0xC0, 0x48, 0x89, 0x05, 0x01, 0x05, 0x07, 0x00, 0x48, 0x89, 0x05}, 6},
	{"__ZN31AppleIntelFramebufferController16getOSInformationEv", "AIFC::getOSInformation", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x53, 0x48, 0x83, 0xEC, 0x18, 0x48, 0x89, 0xFB}, 23},
	{"__ZN31AppleIntelFramebufferController17registerWithAICPMEPv", "AIFC::registerWithAICPM", {0x55, 0x48, 0x89, 0xE5, 0x53, 0x48, 0x83, 0xEC, 0x28, 0x48, 0x89, 0xF3, 0xBE, 0x98, 0x59, 0x14}, 17},
	{"__ZN31AppleIntelFramebufferController13FBMemMgr_InitEv", "AIFC::FBMemMgr_Init", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x55, 0x41, 0x54, 0x53, 0x48, 0x83, 0xEC}, 32},
	{"__ZN31AppleIntelFramebufferController11initCDClockEv", "AIFC::initCDClock", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x53, 0x50, 0x48, 0x89, 0xFB, 0xBE, 0x04, 0x10}, 18},
	{"__ZN14AppleIntelPort13allocatePortsEj", "AppleIntelPort::allocatePorts", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x55, 0x41, 0x54, 0x53, 0x50, 0x48, 0x83}, 14},
	{"__ZN19AppleIntelPowerWell4initEP31AppleIntelFramebufferController", "AppleIntelPowerWell::init", {0x55, 0x48, 0x89, 0xE5, 0x53, 0x50, 0x48, 0x89, 0xFB, 0x48, 0x89, 0x77, 0x10, 0x8A, 0x86, 0x20}, 24},
	{"__ZN19AppleIntelPowerWell20probePowerWellsStateEv", "AppleIntelPowerWell::probePowerWellsState", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x55, 0x41, 0x54, 0x53, 0x48, 0x83, 0xEC}, 33},
	{"__ZN19AppleIntelPowerWell19enableDisplayEngineEv", "AppleIntelPowerWell::enableDisplayEngine", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x53, 0x50, 0x48, 0x89, 0xFB, 0x48, 0x8B, 0x7F}, 22},
	{"__ZN21AppleIntelDisplayPath4initEj", "AppleIntelDisplayPath::init", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x56, 0x53, 0x48, 0x83, 0xEC, 0x10, 0x41, 0x89, 0xF6, 0x48, 0x89}, 23},
	{"__ZN21AppleIntelFramebuffer4initEP31AppleIntelFramebufferControllerj", "AppleIntelFramebuffer::init", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x54, 0x53, 0x48, 0x83, 0xEC, 0x10, 0x41}, 38},
	{"__ZN31AppleIntelFramebufferController23initPlatformWorkaroundsEv", "AIFC::initPlatformWorkarounds", {0x55, 0x48, 0x89, 0xE5, 0x31, 0xC0, 0x83, 0xBF, 0x9C, 0x0C, 0x00, 0x00, 0x00, 0x75, 0x0F, 0xB8}, 13},
	{"__ZN31AppleIntelFramebufferController16setupBootDisplayEv", "AIFC::setupBootDisplay", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x55, 0x41, 0x54, 0x53, 0x48, 0x83, 0xEC}, 37},
	{"__ZN31AppleIntelFramebufferController21hwSetPanelPowerConfigEj", "AIFC::hwSetPanelPowerConfig", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x56, 0x53, 0x48, 0x89, 0xFB, 0x89, 0xB7, 0x00, 0x0D, 0x00, 0x00}, 25},
	{"__ZN31AppleIntelFramebufferController25hwInitializeLatencyValuesEv", "AIFC::hwInitializeLatencyValues", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x56, 0x53, 0x48, 0x89, 0xFB, 0xBE, 0x06, 0x00, 0x00, 0x00, 0x31}, 17},
	{"__ZN31AppleIntelFramebufferController18hwInitializeCStateEv", "AIFC::hwInitializeCState", {0x83, 0xBF, 0x38, 0x0B, 0x00, 0x00, 0x01, 0x0F, 0x85, 0xBA, 0x00, 0x00, 0x00, 0x55, 0x48, 0x89}, 7},
	{"__ZN31AppleIntelFramebufferController19hwSetupCursorMemoryEv", "AIFC::hwSetupCursorMemory", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x55, 0x41, 0x54, 0x53, 0x50, 0x45, 0x31}, 25},
	{"__ZN31AppleIntelFramebufferController13setupWorkLoopEP10IOWorkLoop", "AIFC::setupWorkLoop", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x56, 0x53, 0x48, 0x83, 0xEC, 0x30, 0x49, 0x89, 0xF6, 0x48, 0x89}, 17},
	{"__ZN31AppleIntelFramebufferController15initPMRegistersEv", "AIFC::initPMRegisters", {0xF6, 0x87, 0x20, 0x09, 0x00, 0x00, 0x01, 0x0F, 0x85, 0x2C, 0x0C, 0x00, 0x00, 0x55, 0x48, 0x89}, 7},
	{"__ZN31AppleIntelFramebufferController20hwGetMemoryLayoutEFIEP21AppleIntelFramebuffer", "AIFC::hwGetMemoryLayoutEFI", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x54, 0x53, 0x8B, 0x8E, 0x9C, 0x7D, 0x00}, 34},
	{"__ZN14AppleIntelPAVP4initEP9IOService", "AppleIntelPAVP::init", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x56, 0x53, 0x49, 0x89, 0xF6, 0x48, 0x89, 0xFB, 0x48, 0x8D, 0x05}, 13},
	{"__ZN31AppleIntelFramebufferController15createMEIDriverEv", "AIFC::createMEIDriver", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x53, 0x50, 0x45, 0x31, 0xFF, 0x48, 0x83, 0xBF}, 21},
	{"__ZN31AppleIntelFramebufferController35createAppleGraphicsDeviceControlnubEv", "AIFC::createAppleGraphicsDeviceControlnub", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x53, 0x50, 0x49, 0x89, 0xFE, 0x48, 0x8B, 0x05}, 13},
	{"__ZN31AppleIntelFramebufferController17addPMNotificationEv", "AIFC::addPMNotification", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x53, 0x48, 0x81, 0xEC, 0x28, 0x01, 0x00, 0x00}, 19},
	{"__ZN31AppleIntelFramebufferController18hwEnableInterruptsEv", "AIFC::hwEnableInterrupts", {0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x53, 0x50, 0x48, 0x89, 0xFB, 0xBE, 0x08, 0x44}, 18},
};

const size_t IGFX::TigerLakeFunctionTracer::functionCount = arrsize(functions);

template <size_t I>
uint64_t IGFX::TigerLakeFunctionTracer::wrapFunction(uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3, uint64_t a4, uint64_t a5) {
	auto &tracer = callbackIGFX->modTigerLakeFunctionTracer;
	tracer.onEntry(I);
	auto result = reinterpret_cast<Wrapper>(tracer.org[I])(a0, a1, a2, a3, a4, a5);
	tracer.onReturn(I, result);
	return result;
}

const IGFX::TigerLakeFunctionTracer::Wrapper IGFX::TigerLakeFunctionTracer::wrappers[] {
	wrapFunction<0>,
	wrapFunction<1>,
	wrapFunction<2>,
	wrapFunction<3>,
	wrapFunction<4>,
	wrapFunction<5>,
	wrapFunction<6>,
	wrapFunction<7>,
	wrapFunction<8>,
	wrapFunction<9>,
	wrapFunction<10>,
	wrapFunction<11>,
	wrapFunction<12>,
	wrapFunction<13>,
	wrapFunction<14>,
	wrapFunction<15>,
	wrapFunction<16>,
	wrapFunction<17>,
	wrapFunction<18>,
	wrapFunction<19>,
	wrapFunction<20>,
	wrapFunction<21>,
	wrapFunction<22>,
	wrapFunction<23>,
	wrapFunction<24>,
	wrapFunction<25>,
	wrapFunction<26>
};

void IGFX::TigerLakeFunctionTracer::init() {
	static_assert(arrsize(wrappers) == arrsize(functions), "One wrapper per traced function");
	static_assert(arrsize(functions) <= MaxFunctions, "Too many traced functions");

	// We only need to patch the framebuffer driver
	requiresPatchingFramebuffer = true;
}

void IGFX::TigerLakeFunctionTracer::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	if (!checkKernelArgument("-igfxtgl"))
		return;

	// Proves that this code runs at all and shows what the routing decided. Deliberately not limited to Tiger Lake.
	auto &tracer = callbackIGFX->modTigerLakeTracer;
	if (checkKernelArgument("-igfxtglalive"))
		PANIC("igfx", "TGL: alive 0002 gen=%d fb=%d tracer=%d stop=%u park=%d vesa=%d", static_cast<int>(BaseDeviceInfo::get().cpuGeneration),
			  callbackIGFX->currentFramebuffer == &kextIntelICLLPFb, tracer.enabled, tracer.stopAt, tracer.park, checkKernelArgument("-igfxvesa"));

	if (BaseDeviceInfo::get().cpuGeneration != CPUInfo::CpuGeneration::TigerLake)
		return;

	selfTest = checkKernelArgument("-igfxtglselftest");
	bool hasEntry = PE_parse_boot_argn("igfxtglfn", &stopEntry, sizeof(stopEntry));
	bool hasReturn = PE_parse_boot_argn("igfxtglfnret", &stopReturn, sizeof(stopReturn));
	routing = hasEntry || hasReturn;
	enabled = selfTest || routing;
	if (enabled)
		SYSLOG("igfx", "TGL: fn tracer 0002 selftest=%d routing=%d entry=%u ret=%u", selfTest, routing, stopEntry, stopReturn);
}

void IGFX::TigerLakeFunctionTracer::processFramebufferKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	// WhateverGreen routes getOSInformation itself after all submodules when any of these is set, and the DVMT fix
	// routes FBMemMgr_Init before us. Routing either again would stack two trampolines, so leave them alone.
	auto igfx = callbackIGFX;
	bool coreRoutesOSInformation = igfx->applyFramebufferPatch || igfx->dumpFramebufferToDisk || igfx->dumpPlatformTable || igfx->hdmiAutopatch;

	for (size_t i = 0; i < functionCount; i++) {
		auto &function = functions[i];
		auto from = patcher.solveSymbol(index, function.symbol, address, size, true);
		if (!from) {
			patcher.clearError();
			status[i] = '-';
			continue;
		}
		resolved++;

		if (memcmp(reinterpret_cast<const void *>(from), function.signature, sizeof(function.signature)) != 0) {
			status[i] = 's';
			continue;
		}

		if ((coreRoutesOSInformation && strcmp(function.symbol, "__ZN31AppleIntelFramebufferController16getOSInformationEv") == 0) ||
			(igfx->modDVMTCalcFix.enabled && strcmp(function.symbol, "__ZN31AppleIntelFramebufferController13FBMemMgr_InitEv") == 0)) {
			status[i] = 'w';
			continue;
		}

		if (!routing) {
			status[i] = 'r';
			continue;
		}

		// A long (absolute) route overwrites 14 bytes. When fewer leading bytes are relocatable, only allow a short
		// relative route, which overwrites 5 and fails cleanly when the wrapper is out of range.
		bool shortOnly = function.safeLength < 14;
		size_t copied = Disassembler::quickInstructionSize(from, shortOnly ? 5 : 14);
		if (copied == 0 || copied > function.safeLength) {
			status[i] = 'd';
			continue;
		}

		KernelPatcher::RouteRequest request(function.symbol, wrappers[i], org[i]);
		bool success = shortOnly ? patcher.routeMultipleShort(index, &request, 1, address, size) : patcher.routeMultiple(index, &request, 1, address, size);
		if (!success || !org[i]) {
			patcher.clearError();
			org[i] = 0;
			status[i] = 'f';
			continue;
		}

		status[i] = '+';
		routed++;
	}
	status[functionCount] = '\0';

	for (size_t i = 0; i < functionCount; i++)
		SYSLOG("igfx", "TGL: fn %lu %c %s", i + 1, status[i], functions[i].name);
	SYSLOG("igfx", "TGL: fn table resolved %lu/%lu routed %lu: %s", resolved, functionCount, routed, status);

	if (selfTest) {
		auto &rrs = igfx->modMMIORegistersReadSupport;
		auto &rws = igfx->modMMIORegistersWriteSupport;
		auto &tracer = igfx->modTigerLakeTracer;
		PANIC("igfx", "TGL: selftest 0002 kext=%d rrs=%d rws=%d orgR=%d orgW=%d tracer=%d stop=%u park=%d fn=%d entry=%u ret=%u resolved=%lu/%lu routed=%lu table=%s",
			  igfx->getRealFramebuffer(index) == &kextIntelICLLPFb, rrs.enabled, rws.enabled, rrs.orgReadRegister32 != nullptr, rws.orgWriteRegister32 != nullptr,
			  tracer.enabled, tracer.stopAt, tracer.park, routing, stopEntry, stopReturn, resolved, functionCount, routed, status);
	}
}

void IGFX::TigerLakeFunctionTracer::onEntry(size_t i) {
	auto hit = static_cast<uint32_t>(OSIncrementAtomic(&entries[i])) + 1;
	auto access = static_cast<uint32_t>(callbackIGFX->modTigerLakeTracer.count);
	SYSLOG("igfx", "TGL: fn > %lu %s hit %u access %u", i + 1, functions[i].name, hit, access);
	if (hit != 1 || stopEntry != i + 1)
		return;

	static char head[160];
	snprintf(head, sizeof(head), "igfx TGL: fn stopped on entry %lu/%lu %s (access %u, tracer %d)\n",
			 i + 1, functionCount, functions[i].name, access, callbackIGFX->modTigerLakeTracer.enabled);
	panicWithRing(head);
}

void IGFX::TigerLakeFunctionTracer::onReturn(size_t i, uint64_t result) {
	auto hit = static_cast<uint32_t>(OSIncrementAtomic(&returns[i])) + 1;
	auto access = static_cast<uint32_t>(callbackIGFX->modTigerLakeTracer.count);
	SYSLOG("igfx", "TGL: fn < %lu %s hit %u access %u = 0x%llx", i + 1, functions[i].name, hit, access, result);
	if (hit != 1 || stopReturn != i + 1)
		return;

	static char head[192];
	snprintf(head, sizeof(head), "igfx TGL: fn stopped after return %lu/%lu %s = 0x%llx (access %u, tracer %d)\n",
			 i + 1, functionCount, functions[i].name, result, access, callbackIGFX->modTigerLakeTracer.enabled);
	panicWithRing(head);
}

void IGFX::TigerLakeFunctionTracer::panicWithRing(const char *head) {
	// Same ring line format as the register tracer, so the harness can read both
	auto &tracer = callbackIGFX->modTigerLakeTracer;
	static char report[TigerLakeTracer::RingSize * 40 + 256];
	size_t len = snprintf(report, sizeof(report), "%s", head);
	auto latest = static_cast<uint32_t>(tracer.count);
	for (uint32_t k = latest >= TigerLakeTracer::RingSize ? latest - TigerLakeTracer::RingSize + 1 : 1; k <= latest && len < sizeof(report); k++) {
		auto &access = tracer.ring[k % TigerLakeTracer::RingSize];
		if (access.index != k)
			continue;
		len += snprintf(report + len, sizeof(report) - len, "%u %s 0x%05X = 0x%08X\n", access.index, access.write ? "W" : "R", access.address, access.value);
	}
	PANIC("igfx", "%s", report);
}

// MARK: - Tiger Lake Register Map

namespace TGLReg {
	static constexpr uint32_t TransDdiFuncCtlA = 0x60400;
	static constexpr uint32_t TransDdiFuncCtlB = 0x61400;
	static constexpr uint32_t TransDdiFuncCtlC = 0x62400;
	static constexpr uint32_t TransDdiFuncCtlEdpICL = 0x6F400;
	static constexpr uint32_t TransConfA = 0x70008;
	static constexpr uint32_t TransClkSelA = 0x46140;
	static constexpr uint32_t TransClkSelC = 0x46148;
	static constexpr uint32_t DpTpCtlA_ICL = 0x64040;
	static constexpr uint32_t DpTpCtlA_TGL = 0x60540;
	static constexpr uint32_t DdiBufCtlA = 0x64000;
	static constexpr uint32_t Dpll0Cfgcr0_TGL = 0x164284;
	static constexpr uint32_t Dpll0Cfgcr1_TGL = 0x164288;
	static constexpr uint32_t Dpll1Cfgcr0_TGL = 0x16428C;
	static constexpr uint32_t Dpll1Cfgcr1_TGL = 0x164290;
	static constexpr uint32_t Dssm = 0x51004;
	static constexpr uint32_t Enable = 0x80000000;
	static constexpr uint32_t ModeDpSst = 2U << 24;
	static constexpr uint32_t ModeMask = 7U << 24;
	static constexpr uint32_t PortWidthMask = 7U << 1;
	static constexpr uint32_t DcoFractionMask = 0x7FFFU << 10;

	static inline bool isFuncCtl(uint32_t a) { return a == TransDdiFuncCtlA || a == TransDdiFuncCtlB || a == TransDdiFuncCtlC; }
	static inline bool isClkSel(uint32_t a) { return a >= TransClkSelA && a <= TransClkSelC && (a & 3) == 0; }
	static inline bool isCfgcr0(uint32_t a) { return a == Dpll0Cfgcr0_TGL || a == Dpll1Cfgcr0_TGL; }

	// TRANS_DDI_FUNC_CTL: ICL selects the DDI with `port << 28` (3 bits), TGL with `(port + 1) << 27` (4 bits)
	static inline uint32_t funcCtlToTGL(uint32_t v) {
		if (v == 0)
			return 0;
		uint32_t port = (v >> 28) & 7;
		return (v & ~(0xFU << 27)) | ((port + 1) << 27);
	}
	static inline uint32_t funcCtlToICL(uint32_t v) {
		uint32_t select = (v >> 27) & 0xF;
		return (v & ~(0xFU << 27)) | ((select ? select - 1 : 0) << 28);
	}
	// TRANS_CLK_SEL: ICL `(port + 1) << 29`, TGL `(port + 1) << 28`
	static inline uint32_t clkSelToTGL(uint32_t v) { return ((v >> 29) & 7) << 28; }
	static inline uint32_t clkSelToICL(uint32_t v) { return ((v >> 28) & 7) << 29; }
	static inline uint32_t halveFraction(uint32_t v) {
		uint32_t f = (v & DcoFractionMask) >> 10;
		return (v & ~DcoFractionMask) | (((f + 1) / 2) << 10);
	}
	static inline uint32_t doubleFraction(uint32_t v) {
		uint32_t f = ((v & DcoFractionMask) >> 10) * 2;
		return (v & ~DcoFractionMask) | ((f > 0x7FFF ? 0x7FFF : f) << 10);
	}
}

void IGFX::TigerLakeRegisterMap::init() {
	requiresPatchingFramebuffer = true;
	requiresPatchingGraphics = true;
	requiresMMIORegistersReadAccess = true;
	requiresMMIORegistersWriteAccess = true;
}


void IGFX::TigerLakeRegisterMap::processGraphicsKext(
    KernelPatcher &patcher, size_t index,
    mach_vm_address_t address, size_t size) {

    uint32_t subslices = 0;
    bool applySubslices = PE_parse_boot_argn("igfxtglss", &subslices, sizeof(subslices))
        && subslices > 0 && subslices <= 8;

    if (csbMode && csbCall) {
        // The four handlers the driver dispatches to, in the order of its table pfnCsbProcessContextSwitchType
        static const char *handlers[4] = {
            "__ZN26IGHardwareCommandStreamer522csbProcessIdleToActiveEPK28SGfxContextStatusBufferEntry",
            "__ZN26IGHardwareCommandStreamer519csbProcessPreemptedEPK28SGfxContextStatusBufferEntry",
            "__ZN26IGHardwareCommandStreamer523csbProcessElementSwitchEPK28SGfxContextStatusBufferEntry",
            "__ZN26IGHardwareCommandStreamer522csbProcessActiveToIdleEPK28SGfxContextStatusBufferEntry"
        };
        csbRec.hooked = 1;
        for (size_t i = 0; i < arrsize(handlers); i++) {
            csbHandlers[i] = reinterpret_cast<CsbHandler>(patcher.solveSymbol(index, handlers[i], address, size));
            if (!csbHandlers[i]) {
                SYSLOG("igfx", "TGLMAP: cannot resolve %s (%d).", handlers[i], patcher.getError());
                patcher.clearError();
                csbRec.hooked = 2;
            }
        }
        if (csbRec.hooked == 1) {
            KernelPatcher::RouteRequest request("__ZN26IGHardwareCommandStreamer526processContextStatusBufferEj", wrapProcessContextStatusBuffer, orgProcessContextStatusBuffer);
            if (!patcher.routeMultiple(index, &request, 1, address, size)) {
                SYSLOG("igfx", "TGLMAP: cannot route processContextStatusBuffer (%d).", patcher.getError());
                patcher.clearError();
                csbRec.hooked = 3;
            } else {
                SYSLOG("igfx", "TGLMAP: reading the context status buffer in the Gen12 layout.");
            }
        } else {
            SYSLOG("igfx", "TGLMAP: context status buffer reader NOT installed (hooked=%u), the driver's reader stays in place.", csbRec.hooked);
            csbMode = 0;
        }
        if (csbLog) {
            // Put the outcome on disk even if the reader is never called. The data volume is not mounted this
            // early, so the write may not land; the result is also readable from the live record.
            uint64_t deadline = 0;
            clock_interval_to_deadline(15, kSecondScale, &deadline);
            csbNextFlush = deadline;
            thread_call_enter_delayed(csbCall, deadline);
        }
    } else if (csbLog) {
        // Log-only boot argument: report that the reader was not requested instead of writing nothing silently.
        csbRec.hooked = 9;
        SYSLOG("igfx", "TGLMAP: igfxtglcsblog=1 without igfxtglcsb; no CSB reader installed.");
    }

    if (hangDump && hangRec && hangCall) {
        // igfxtglhang=1: route the driver's hang analysis and the forcewake call it uses around its
        // register dumps. This capture runs inside that window; it writes no MMIO itself.
        if (bridgeState == 0)
            readHostBridge(); // TOLUD/TSEGMB/BDSM/BGSM fences (validated; junk values ignored)
        if (bridgeState != 1)
            SYSLOG("igfx", "TGLMAP: host bridge fences unavailable; the capture will fail closed (no physical reads).");
        accelSafeForceWake = reinterpret_cast<void (*)(void *, bool, uint32_t)>(patcher.solveSymbol(index, "__ZN16IntelAccelerator13SafeForceWakeEbj", address, size));
        if (!accelSafeForceWake) {
            SYSLOG("igfx", "TGLMAP: cannot resolve SafeForceWake (%d); hang capture off.", patcher.getError());
            patcher.clearError();
            hangDump = 0;
        } else {
            KernelPatcher::RouteRequest requests[2] = {
                { "__ZN20IGHardwareRingBuffer14doHangAnalysisEv", wrapDoHangAnalysis, orgDoHangAnalysis },
                { "__ZN16IntelAccelerator13SafeForceWakeEbj", wrapSafeForceWake, orgSafeForceWake }
            };
            for (size_t hi = 0; hi < arrsize(requests); hi++) {
                if (!patcher.routeMultiple(index, &requests[hi], 1, address, size)) {
                    SYSLOG("igfx", "TGLMAP: cannot route %s (%d); hang capture off.", requests[hi].symbol, patcher.getError());
                    patcher.clearError();
                    hangDump = 0;
                }
            }
            if (hangDump)
                SYSLOG("igfx", "TGLMAP: read-only GPU hang capture armed.");
        }
    }

    if (!applySubslices)
        return;

    static const uint8_t find[] = {
        0x44, 0x89, 0xF8, 0xF7, 0xD0,
        0xF3, 0x0F, 0xB8, 0xF0,
        0x89, 0xB3, 0x88, 0x11, 0x00, 0x00
    };

    uint8_t replace[] = {
        0x44, 0x89, 0xF8, 0xBE, 0x00,
        0x00, 0x00, 0x00, 0x90,
        0x89, 0xB3, 0x88, 0x11, 0x00, 0x00
    };

    replace[4] = static_cast<uint8_t>(subslices);

    KernelPatcher::LookupPatch patch {};
    patch.kext = callbackIGFX->currentGraphics;
    patch.find = find;
    patch.replace = replace;
    patch.size = sizeof(find);
    patch.count = 1;

    patcher.applyLookupPatch(
        &patch, reinterpret_cast<uint8_t *>(address), size
    );

    if (patcher.getError() != KernelPatcher::Error::NoError) {
        SYSLOG("igfx", "TGLMAP: subslice patch failed (%d).",
            patcher.getError());
        patcher.clearError();
    } else {
        SYSLOG("igfx",
            "TGLMAP: IntelAccelerator::getGPUInfo will report %u subslices.",
            subslices);
    }
}

static uint32_t tglUptimeMilliseconds() {
	uint64_t t = 0, nanos = 0;
	clock_get_uptime(&t);
	absolutetime_to_nanoseconds(t, &nanos);
	return static_cast<uint32_t>(nanos / 1000000ULL);
}

/**
 *  Diagnostic writer, delayed thread call. The file is opened, written and closed here: no vnode stays open, so
 *  shutdown cannot hang on it. Runs only when igfxtglcsblog=1; without it the record stays in memory. Nothing
 *  here runs in the MMIO hook.
 */
void IGFX::TigerLakeRegisterMap::csbThread(thread_call_param_t param0, thread_call_param_t) {
	auto self = static_cast<TigerLakeRegisterMap *>(param0);
	if (self->csbLog && self->csbCall) {
		self->csbRec.nowMs = tglUptimeMilliseconds();
		self->csbRec.flushes++;
		FileIO::writeBufferToFile("/Users/Shared/tgl-csb.bin", &self->csbRec, sizeof(self->csbRec));
		self->csbNextFlush = 0;
		self->csbPending = 0;
	}
}

void IGFX::TigerLakeRegisterMap::csbFlush() {
	// One write a second at most, and one thread call in flight at a time: the hook only sets a flag and, when no
	// write is armed yet, a delayed deadline. No blocking call and no disk access from here.
	if (!csbLog || !csbCall || !csbPending)
		return;
	uint64_t now = 0;
	clock_get_uptime(&now);
	if (csbNextFlush != 0) {
		if (now < csbNextFlush)
			return;
		csbNextFlush = 0;
	}
	thread_call_enter1(csbCall, nullptr);
}

/**
 *  Context id of a work item in one of the driver's execlist slots: item -> IGHardwareContext, id at +0x7C
 *  (what ContextStatusBufferValidate compares with bits 15:5 of the entry's upper dword)
 */
static uint16_t tglCsbItemId(void *item) {
	if (!item)
		return 0xFFFF;
	auto context = getMember<uint8_t *>(item, 0);
	return context ? static_cast<uint16_t>(getMember<uint32_t>(context, 0x7C)) : 0xFFFE;
}

void IGFX::TigerLakeRegisterMap::csbNote(void *that, uint8_t action, uint32_t index, uint32_t writePointer, uint32_t lo, uint32_t hi, uint32_t synth, uint32_t flags) {
	uint32_t group = action >> 4;
	uint32_t count = static_cast<uint32_t>(OSIncrementAtomic(reinterpret_cast<volatile SInt32 *>(&csbRec.counts[group & 7]))) + 1;
	csbRec.lastEventMs = tglUptimeMilliseconds();
	if (!csbLog)
		return;
	bool anomaly = group != 0 && group != (CsbRecord::AfterReset >> 4);
	// Keep the first events and every anomaly; an empty buffer after a reset is polled, so only its first few
	if (group == (CsbRecord::AfterReset >> 4) && count > 16)
		return;
	// A stuck entry is polled too (the reference run GA3 filled the log with it)
	if (group == (CsbRecord::NotWritten >> 4) && count > 64)
		return;
	if (csbRec.next >= (anomaly ? CsbRecord::Size : CsbRecord::NormalLimit)) {
		if ((count & 0x3FF) == 0)
			csbFlush();
		return;
	}
	uint32_t slot = static_cast<uint32_t>(OSIncrementAtomic(reinterpret_cast<volatile SInt32 *>(&csbRec.next)));
	if (slot >= CsbRecord::Size)
		return;
	auto &e = csbRec.entry[slot];
	auto lists = reinterpret_cast<void **>(static_cast<uint8_t *>(that) + 0x30);
	uint32_t active = getMember<uint32_t>(that, 0x50) & 1;
	e.ms = tglUptimeMilliseconds();
	e.engine = *getMember<uint8_t *>(that, 0x28);
	e.action = action;
	e.index = static_cast<uint8_t>(index);
	e.writePointer = static_cast<uint8_t>(writePointer);
	e.lo = lo;
	e.hi = hi;
	e.synth = synth;
	e.active[0] = tglCsbItemId(lists[active * 2]);
	e.active[1] = tglCsbItemId(lists[active * 2 + 1]);
	e.pending[0] = tglCsbItemId(lists[(1 - active) * 2]);
	e.pending[1] = tglCsbItemId(lists[(1 - active) * 2 + 1]);
	e.flags = flags;
	csbPending++;
	if (csbNextFlush == 0) {
		// Arm the delayed writer; it is reset only by the writer, so at most one write a second is scheduled.
		clock_interval_to_deadline(1, kSecondScale, &csbNextFlush);
		thread_call_enter_delayed(csbCall, csbNextFlush);
	}
}

void IGFX::TigerLakeRegisterMap::wrapProcessContextStatusBuffer(void *that, uint32_t flags) {
	// Offsets are those of IGHardwareCommandStreamer5 in AppleIntelICLGraphics 24.0.5:
	//   +0x10 IntelAccelerator, +0x28 engine description (byte 0 = IGHwCsType), +0x30 two execlists of two work
	//   items each, +0x50 index of the active list, +0x68 hardware status page, +0x1C04 read pointer.
	// Hardware status page (same on Gen11 and Gen12): entries at +0x40, write pointer at +0xBC.
	// Six entries: the driver leaves GFX_MODE bit 3 clear, and the reference run GA3 showed the hardware wrap
	// from entry 5 to entry 0 with entries 6-11 never written. Only the layout of an entry is the Gen12 one.
	static constexpr uint32_t Entries = 6;
	static constexpr uint32_t IdleId = 0x7FF;
	static constexpr uint32_t Stored = 0x10; // the read pointer is kept at +0x1C04 as Stored + index
	auto self = &callbackIGFX->modTigerLakeRegisterMap;
	auto cs = static_cast<uint8_t *>(that);
	auto accel = getMember<uint8_t *>(that, 0x10);
	auto page = getMember<volatile uint32_t *>(that, 0x68);
	auto &rec = self->csbRec;
	if (OSIncrementAtomic(reinterpret_cast<volatile SInt32 *>(&rec.calls)) == 0)
		rec.accelFlags = getMember<uint32_t>(accel, 0x11C0);

	// The driver reads the buffer through MMIO when bit 7 of this byte is set; that path is left to the driver
	if (!page || (accel[0x11C0] & 0x80)) {
		self->csbNote(that, CsbRecord::Passthrough, 0, 0, 0, 0, 0, flags);
		FunctionCast(wrapProcessContextStatusBuffer, self->orgProcessContextStatusBuffer)(that, flags);
		return;
	}

	uint32_t writePointer = page[0xBC / 4];
	auto &stored = *reinterpret_cast<uint32_t *>(cs + 0x1C04);
	uint32_t readPointer;
	if (stored >= Stored && stored < Stored + Entries) {
		readPointer = stored - Stored;
	} else {
		// The driver put its reset value (7) here, in init(), resetOnWake() or processGPUReset(); the last two
		// also write 7 to the write pointer in the page. After a reset the hardware's next entry is entry 0.
		// Entries read here are overwritten with all ones, the page starts out zeroed, and the first entry after
		// a reset is an idle-to-active one with bit 0 set: an entry 0 of zeros or ones is not new.
		uint32_t lo = page[0x40 / 4], hi = page[0x44 / 4];
		if ((lo == 0 && hi == 0) || (lo == 0xFFFFFFFF && hi == 0xFFFFFFFF)) {
			self->csbNote(that, CsbRecord::AfterReset, 0, writePointer, lo, hi, stored, flags);
			return;
		}
		readPointer = Entries - 1;
	}
	if (writePointer >= Entries) {
		self->csbNote(that, CsbRecord::BadPointer, readPointer, writePointer, 0, 0, stored, flags);
		return;
	}

	while (readPointer != writePointer) {
		uint32_t index = readPointer + 1 == Entries ? 0 : readPointer + 1;
		volatile uint32_t *entry = page + 0x40 / 4 + index * 2;
		uint32_t lo = entry[0], hi = entry[1];
		// The write pointer can be visible before the entry is (i915 csb_read/wa_csb_read, Tiger Lake)
		for (uint32_t spins = 0; (lo == 0xFFFFFFFF || hi == 0xFFFFFFFF) && spins < 20; spins++) {
			IODelay(10);
			lo = entry[0];
			hi = entry[1];
		}
		if (lo == 0xFFFFFFFF || hi == 0xFFFFFFFF) {
			self->csbNote(that, CsbRecord::NotWritten, index, writePointer, lo, hi, 0, flags);
			return;
		}
		entry[0] = 0xFFFFFFFF;
		entry[1] = 0xFFFFFFFF;
		readPointer = index;
		stored = Stored + readPointer;

		uint32_t to = (lo >> 15) & 0x7FF, away = (hi >> 15) & 0x7FF, detail = hi & 0xF;
		bool newQueue = (lo & 1) != 0;
		auto lists = reinterpret_cast<void **>(cs + 0x30);
		uint32_t active = getMember<uint32_t>(that, 0x50) & 1;
		uint32_t active0 = tglCsbItemId(lists[active * 2]), active1 = tglCsbItemId(lists[active * 2 + 1]);
		uint32_t pending0 = tglCsbItemId(lists[(1 - active) * 2]);
		// Gen8 event bits: 0 idle to active, 1 preempted, 2 element switch, 3 active to idle, 4 context complete,
		// 7 wait on semaphore, 15 lite restore
		uint32_t waitOrDone = detail == 4 ? 0x80 : 0x10;
		uint8_t action;
		uint32_t synth[2];
		bool fits;
		if (away == IdleId && to == IdleId) {
			self->csbNote(that, CsbRecord::BothIdle, index, writePointer, lo, hi, 0, flags);
			continue;
		} else if (away == IdleId) {
			action = CsbRecord::IdleToActive;
			synth[0] = 0x1;
			synth[1] = to << 5;
			fits = pending0 == to;
		} else if (newQueue) {
			action = CsbRecord::Preempted;
			synth[0] = 0x2 | (to == away ? 0x8000 : (detail == 0 ? 0x10 : (detail == 4 ? 0x80 : 0)));
			synth[1] = away << 5;
			fits = active0 == away && pending0 != 0xFFFF;
		} else if (to != IdleId) {
			// The handler dereferences the second slot of the active list without a check
			action = CsbRecord::ElementSwitch;
			synth[0] = 0x4 | waitOrDone;
			synth[1] = away << 5;
			fits = active0 == away && active1 == to;
		} else {
			action = CsbRecord::ActiveToIdle;
			synth[0] = 0x8 | waitOrDone;
			synth[1] = away << 5;
			fits = active0 == away;
		}
		if (!fits) {
			self->csbNote(that, CsbRecord::Skipped + action, index, writePointer, lo, hi, synth[0], flags);
			continue;
		}
		self->csbNote(that, action, index, writePointer, lo, hi, synth[0], flags);
		self->csbHandlers[action - 1](that, synth);
	}
}

/**
 *  Physical read used by the hang capture. The capture core asks only for approved ranges; this
 *  re-checks the classifier/fences and then goes through the kernel's physical-address descriptor.
 *  There is no path in this kext that reads physical memory without hangPageAllowed() first.
 */
bool IGFX::TigerLakeRegisterMap::hangReadPhysical(void *context, uint64_t physical, void *dst, uint64_t length) {
	auto self = static_cast<TigerLakeRegisterMap *>(context);
	if (!hangPageAllowed(self, physical, length))
		return false;
	auto md = IOMemoryDescriptor::withPhysicalAddress(static_cast<IOPhysicalAddress>(physical),
		static_cast<IOByteCount>(length), kIODirectionOut);
	if (!md)
		return false;
	bool ok = md->readBytes(0, dst, static_cast<IOByteCount>(length)) == static_cast<IOByteCount>(length);
	md->release();
	return ok;
}

/**
 *  The GA3.1 approval rule. Fences never approve; the kernel's pmap_valid_page() is the authority
 *  and every 4 KiB page of the range must be a kernel-managed usable page.
 */
bool IGFX::TigerLakeRegisterMap::hangPageAllowed(void *context, uint64_t address, uint64_t length) {
	auto self = static_cast<TigerLakeRegisterMap *>(context);
	if (!self->pmapValidPage)
		return false;
	if (length == 0 || length > TglHang::PageSize)
		return false;                       // one page at a time, by contract
	if (address >= TglHang::MaxPhysical || length > TglHang::MaxPhysical - address)
		return false;                       // overflow, or beyond the 32-bit ppnum_t space
	if (!TglHang::fencesAllow(self->hangFences, address, length)) {
		self->fenceRejected++; // GA3.3: attribute the refusal
		return false;
	}
	uint64_t end = address + length;
	for (uint64_t page = address & ~(TglHang::PageSize - 1); page < end; page += TglHang::PageSize) {
		// Alignment and range are checked before the conversion; the page number is never truncated.
		uint32_t ppn = 0;
		if (!TglHang::toPpnum(page, ppn))
			return false;
		self->pmapChecked++; // GA3.3
		if (!self->pmapValidPage(ppn)) {
			self->pmapRejected++;
			return false;
		}
		self->pmapAccepted++;
	}
	return true;
}

/**
 *  Host bridge (BDF 00:00.0) fences: TOLUD (0xBC), TSEGMB (0xB8), BDSM (0xB0), BGSM (0xB4).
 *  Read once at kext load; validated values become extra refusals, junk values are ignored.
 */
void IGFX::TigerLakeRegisterMap::readHostBridge() {
	bridgeState = 2;
	auto matching = IOService::serviceMatching("IOPCIDevice");
	if (!matching)
		return;
	auto iter = IOService::getMatchingServices(matching);
	matching->release();
	if (!iter)
		return;
	IOPCIDevice *bridge = nullptr;
	while (auto obj = iter->getNextObject()) {
		auto dev = OSDynamicCast(IOPCIDevice, obj);
		if (!dev)
			continue;
		uint32_t vid = 0, did = 0;
		if (auto d = OSDynamicCast(OSData, dev->getProperty("vendor-id")); d && d->getLength() >= 4)
			vid = *static_cast<const uint32_t *>(d->getBytesNoCopy());
		if (auto d = OSDynamicCast(OSData, dev->getProperty("device-id")); d && d->getLength() >= 4)
			did = *static_cast<const uint32_t *>(d->getBytesNoCopy());
		if (vid == 0x8086 && did == 0x9A14) { // Tiger Lake host bridge / DRAM controller
			bridge = dev;
			break;
		}
	}
	iter->release();
	if (!bridge)
		return;
	bridgeTolud = bridge->configRead32(0xBC);
	bridgeTsegmb = bridge->configRead32(0xB8);
	bridgeBdsm = bridge->configRead32(0xB0);
	bridgeBgsm = bridge->configRead32(0xB4);
	bridgeState = 1;
	SYSLOG("igfx", "TGLMAP: host bridge fences TOLUD=0x%X TSEGMB=0x%X BDSM=0x%X BGSM=0x%X.",
		bridgeTolud, bridgeTsegmb, bridgeBdsm, bridgeBgsm);
}

/**
 *  One bounded capture attempt. Runs inside the driver's own forcewake window: only reads happen here,
 *  no file I/O and no register writes.
 */
void IGFX::TigerLakeRegisterMap::hangCapture(void *accel, uint32_t attempts) {
	if (!hangRec || hangCount >= HangRecord::MaxRecords)
		return;
	auto &r = hangRec[hangCount];
	bzero(&r, sizeof(r));
	r.magic = HangRecord::Magic;
	r.index = hangCount;
	r.ms = tglUptimeMilliseconds();
	r.attempts = attempts;
	r.resolveDiag = resolveDiag; // GA3.2: classifier resolution outcome for this boot

	// The accelerator keeps its MMIO mapping at +0x1270 (IntelAccelerator::SafeReadRegister32 uses it).
	auto mmio = getMember<uint8_t *>(accel, 0x1270);
	if (!mmio) {
		r.out.result = TglHang::RegsInvalid;
		return;
	}
	static const uint32_t hangRegisters[16] = {
		0x2140, 0x2168, 0x2270, 0x2274, 0x2074, 0x2068, 0x2034, 0x2030,
		0x2038, 0x206C, 0x229C, 0x20C8, 0x2180, 0x2234, 0x7100, 0x20B0
	};
	TglHang::CaptureInput in {};
	for (size_t i = 0; i < arrsize(hangRegisters); i++) {
		in.regs[i] = *reinterpret_cast<volatile uint32_t *>(mmio + hangRegisters[i]);
		r.regs[i] = in.regs[i];
	}
	in.ggc = *reinterpret_cast<volatile uint32_t *>(mmio + 0x108040);
	r.ggc = in.ggc;
	r.dsmLo = *reinterpret_cast<volatile uint32_t *>(mmio + 0x1080C0);
	r.dsmHi = *reinterpret_cast<volatile uint32_t *>(mmio + 0x1080C4);
	in.dsmBase = (static_cast<uint64_t>(r.dsmHi) << 32) | r.dsmLo;
	if (maxMemAddr != 0) {
		in.maxMem = getMember<uint64_t>(reinterpret_cast<uint8_t *>(maxMemAddr), 0);
		in.haveMaxMem = true;
		r.maxMem = in.maxMem;
	}
	in.tolud = bridgeTolud;
	in.tsegmb = bridgeTsegmb;
	in.bdsm = bridgeBdsm;
	in.bgsm = bridgeBgsm;
	in.bridgeValid = bridgeState == 1;
	in.requireExclusions = true; // fail closed unless stolen+TOLUD+TSEG are all proven
	in.classifierReady = pmapValidPage != nullptr;
	in.classifierProbeOk = (pmapValidPage && classifierProbe0 == 0) ? 1 : 0;
	in.classifierProbe1 = classifierProbe1;
	uint64_t stolenBase = 0, stolenSize = 0;
	bool haveStolen = TglHang::parseStolen(in.ggc, in.dsmBase, stolenBase, stolenSize);
	TglHang::deriveFences(in.tolud, in.tsegmb, in.bdsm, in.bgsm, haveStolen, stolenBase, stolenSize,
	    in.haveMaxMem, in.maxMem, in.fences);
	hangFences = in.fences;

	// GA3.3: reset the classifier counters for this attempt
	pmapChecked = pmapAccepted = pmapRejected = fenceRejected = 0;

	TglHang::Reader reader {};
	reader.context = this;
	reader.read = hangReadPhysical;
	reader.allow = hangPageAllowed;
	reader.allowContext = this;
	TglHang::capture(reader, in, r.out);
	TglHang::finishCounters(reader, r.out);

	// GA3.3: fill the diagnostics. Every value is an observation of the run, nothing is inferred.
	r.diag.version = TglHang::RecordVersion;
	r.diag.size = sizeof(HangRecord);
	r.diag.stage = reader.stage;
	r.diag.failReason = reader.failSeen ? reader.failReason : static_cast<uint32_t>(r.out.result);
	r.diag.failLevel = reader.failLevel;
	r.diag.pmapChecked = pmapChecked;
	r.diag.pmapAccepted = pmapAccepted;
	r.diag.pmapRejected = pmapRejected;
	r.diag.fenceRejected = fenceRejected;
	r.diag.readAttempts = reader.readAttempts;
	r.diag.readSuccesses = reader.readSuccesses;
	r.diag.batchBytes = r.out.batchPages * static_cast<uint32_t>(TglHang::PageSize);
	r.diag.vsBytes = r.out.kernelPages[0] * static_cast<uint32_t>(TglHang::PageSize);
	r.diag.psBytes = r.out.kernelPages[1] * static_cast<uint32_t>(TglHang::PageSize);
	r.diag.bridgeDiag = (bridgeState == 1 ? 1U : 0U) |
	    ((r.out.exclusionStolen ? 1U : 0U) << 1) | ((r.out.exclusionLowTop ? 1U : 0U) << 2) |
	    ((r.out.exclusionTseg ? 1U : 0U) << 3) | (r.out.bridgeValid << 4) |
	    ((bridgeState & 0xFFU) << 8);
	r.diag.failGpuVA = reader.failGpuVA;
	r.diag.failPhys = reader.failPhys;
	r.diag.failTable = reader.failTable;
}

uint32_t IGFX::TigerLakeRegisterMap::wrapDoHangAnalysis(void *that) {
	auto self = &callbackIGFX->modTigerLakeRegisterMap;
	if (!self->hangDump || !self->hangRec || !self->hangCall || self->hangCount >= HangRecord::MaxRecords)
		return FunctionCast(wrapDoHangAnalysis, self->orgDoHangAnalysis)(that);

	self->hangInProgress = 1;
	self->hangAttempts = 0;
	self->hangCaptured = 0;
	self->hangWakes = 0;
	self->hangWakesRejected = 0;
	self->hangWakeDomain = 0;
	uint32_t result = FunctionCast(wrapDoHangAnalysis, self->orgDoHangAnalysis)(that);
	self->hangInProgress = 0;

	// If no window produced a record, keep the outcome as a failure record so the reason reaches the
	// user instead of disappearing. Nothing else is done with the hung state.
	if (!self->hangCaptured && self->hangCount < HangRecord::MaxRecords) {
		if (self->hangAttempts > 0) {
			self->hangCount++;
			thread_call_enter1(self->hangCall, nullptr);
		} else if (self->hangWakesRejected > 0) {
			auto &r = self->hangRec[self->hangCount];
			bzero(&r, sizeof(r));
			r.magic = HangRecord::Magic;
			r.index = self->hangCount;
			r.ms = tglUptimeMilliseconds();
			r.wakeDomain = self->hangWakeDomain;
			r.out.result = TglHang::WakesUnusable;
			self->hangCount++;
			thread_call_enter1(self->hangCall, nullptr);
		}
	}
	return result;
}

void IGFX::TigerLakeRegisterMap::wrapSafeForceWake(void *that, bool enable, uint32_t domain) {
	auto self = &callbackIGFX->modTigerLakeRegisterMap;
	FunctionCast(wrapSafeForceWake, self->orgSafeForceWake)(that, enable, domain);
	if (!enable || !self->hangInProgress || !self->hangRec)
		return;
	self->hangWakes++;
	if (self->hangWakeDomain == 0)
		self->hangWakeDomain = domain;
	// Only the render forcewake domain the driver itself uses before its register dumps is accepted.
	// No other window is assumed to make the captured registers readable.
	if (domain != 7) {
		self->hangWakesRejected++;
		return;
	}
	if (self->hangCaptured || self->hangCount >= HangRecord::MaxRecords || self->hangAttempts >= 4)
		return;
	self->hangAttempts++;
	self->hangCapture(that, self->hangAttempts);
	auto &r = self->hangRec[self->hangCount];
	r.wakeDomain = domain; // GA3.2: the window that produced this attempt (7 = render forcewake)
	if (r.attempts < arrsize(r.attemptReasons))
		r.attemptReasons[r.attempts - 1] = r.out.result;
	if (r.out.result == TglHang::Ok) {
		self->hangCaptured = 1;
		self->hangCount++;
		thread_call_enter1(self->hangCall, nullptr);
	}
}

/**
 *  Independent hang-record writer with a complete cleanup path. The GA3.1 build deliberately does
 *  not call FileIO::writeBufferToFile() here: that Lilu helper skips vnode_close() when the write
 *  fails, which would leak the open vnode. This implementation closes the vnode on every path
 *  after a successful vnode_open(), always releases the vfs context and the uio it creates, and
 *  reports the filesystem error upwards.
 *
 *  Context: called from the hang thread call only (kernel thread context). Nothing here runs
 *  inside the GPU hook.
 */
int IGFX::TigerLakeRegisterMap::hangWriteRecords(const void *data, size_t length) {
	vfs_context_t ctx = vfs_context_create(nullptr);
	if (!ctx)
		return ENOMEM;

	int error = 0;
	vnode_t vp = nullptr;
	error = vnode_open("/Users/Shared/tgl-hang.bin",
		O_WRONLY | O_CREAT | O_TRUNC | FWRITE | O_NOFOLLOW, 0666, VNODE_LOOKUP_NOFOLLOW, &vp, ctx);
	if (error == 0 && vp) {
		uio_t uio = uio_create(1, 0, UIO_SYSSPACE, UIO_WRITE);
		if (!uio) {
			error = ENOMEM;
		} else {
			if (uio_addiov(uio, CAST_USER_ADDR_T(data), length) != 0) {
				error = EINVAL;
			} else {
				error = VNOP_WRITE(vp, uio, IO_SYNC, ctx);
				if (error == 0 && uio_resid(uio) != 0)
					error = EIO;         // short write: the file is never treated as complete
			}
			if (uioFree)
				uioFree(uio);
			else
				SYSLOG("igfx", "TGLMAP: uio_free unresolved; the uio object of this write is not released.");
		}
		// Every exit path after a successful open closes the vnode, the write-error path included.
		// vnode_close() runs vn_close() and then vnode_put(), so the open reference is released
		// even when the filesystem's close returns an error (bsd/vfs/vfs_subr.c).
		int closeError = vnode_close(vp, FWASWRITTEN, ctx);
		if (closeError != 0) {
			SYSLOG("igfx", "TGLMAP: vnode_close failed (%d); the open reference was still released.", closeError);
			if (error == 0)
				error = closeError;
		}
	} else if (error == 0) {
		error = EIO;                         // vnode_open reported success without a vnode
	}
	vfs_context_rele(ctx);
	return error;
}

void IGFX::TigerLakeRegisterMap::hangThread(thread_call_param_t param0, thread_call_param_t) {
	// Kernel thread context: the file is opened, written and closed inside this call only.
	auto self = static_cast<TigerLakeRegisterMap *>(param0);
	if (!self->hangRec || !self->hangWriteBuf || self->hangCount == 0)
		return;
	if (self->hangWriteError != 0)
		return; // single attempt per boot: a failed write is never retried
	if (OSCompareAndSwap(0, 1, &self->hangWriting))
		return; // one writer at a time (the kernel also coalesces pending thread calls)
	uint32_t count = self->hangCount < HangRecord::MaxRecords ? self->hangCount : HangRecord::MaxRecords;
	size_t length = sizeof(HangRecord) * static_cast<size_t>(count);
	// Snapshot of the completed records: slot `count` and later may still be filled by a capture,
	// so the filesystem never reads memory a capture may be modifying.
	lilu_os_memcpy(self->hangWriteBuf, self->hangRec, length);
	int err = self->hangWriteRecords(self->hangWriteBuf, length);
	self->hangWriting = 0;
	self->hangWriteError = err;
	if (err != 0)
		SYSLOG("igfx", "TGLMAP: hang record write failed (%d); records stay in wired memory and further writes are disabled for this boot.", err);
}

void IGFX::TigerLakeRegisterMap::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	// GA3.2 fix: the hang-capture boot argument must be known before the classifier symbols are
	// resolved. In GA3.1 the parse sat after this resolution block and the block therefore never
	// ran on the single processKernel invocation; every capture then failed closed with
	// MemoryMapUnverified (confirmed by both GA3.1b records).
	PE_parse_boot_argn("igfxtglhang", &hangDump, sizeof(hangDump));
	if (hangDump) {
		if (maxMemAddr == 0) {
			// Upper sanity bound only; this value never approves a read by itself.
			maxMemAddr = patcher.solveSymbol(KernelPatcher::KernelID, "_max_mem");
			if (!maxMemAddr) {
				resolveError = static_cast<uint32_t>(patcher.getError());
				SYSLOG("igfx", "TGLMAP: cannot resolve _max_mem (%d); only the lower bound applies.", patcher.getError());
				patcher.clearError();
			}
		}
		if (pmapValidPage == nullptr) {
			// The kernel's own usable-page classifier (built from the EFI memory map by i386_vm_init;
			// the kernel itself uses it in KDP and hibernation before touching a physical page).
			// Without it every physical read is refused and the capture records MemoryMapUnverified.
			pmapValidAddr = patcher.solveSymbol(KernelPatcher::KernelID, "_pmap_valid_page");
			if (pmapValidAddr) {
				pmapValidPage = reinterpret_cast<uint32_t (*)(uint32_t)>(pmapValidAddr);
				classifierProbe0 = pmapValidPage(0) ? 1 : 0;
				classifierProbe1 = pmapValidPage(0x40000) ? 1 : 0;
				SYSLOG("igfx", "TGLMAP: page classifier ready (page0 %s, 1GiB %s).",
					classifierProbe0 ? "UNEXPECTED-valid" : "invalid", classifierProbe1 ? "valid" : "invalid");
			} else {
				resolveError = static_cast<uint32_t>(patcher.getError());
				SYSLOG("igfx", "TGLMAP: cannot resolve _pmap_valid_page (%d); physical reads will be refused.", patcher.getError());
				patcher.clearError();
			}
		}
		if (uioFree == nullptr) {
			// The writer releases every uio it creates through the kernel's own uio_free; the
			// symbol is resolved here so the kext never links against a symbol it cannot see.
			uioFreeAddr = patcher.solveSymbol(KernelPatcher::KernelID, "_uio_free");
			if (uioFreeAddr)
				uioFree = reinterpret_cast<void (*)(void *)>(uioFreeAddr);
			else {
				resolveError = static_cast<uint32_t>(patcher.getError());
				SYSLOG("igfx", "TGLMAP: cannot resolve _uio_free (%d); a created uio will not be released.", patcher.getError());
				patcher.clearError();
			}
		}
		// GA3.2: keep the outcome inside the kext so the next capture record proves what happened.
		resolveDiag = TglHang::packResolveDiag(maxMemAddr != 0, pmapValidPage != nullptr,
		    pmapValidPage != nullptr && classifierProbe0 == 0, uioFree != nullptr, resolveError);
	}
	uint32_t mask = 0;
	if (!PE_parse_boot_argn("igfxtglmap", &mask, sizeof(mask)))
		mask = checkKernelArgument("-igfxtglmap") ? AllTranslation : 0;
	if (mask == 0)
		return;

	uint32_t levelMax = 0;
	if (PE_parse_boot_argn("igfxtglblmax", &levelMax, sizeof(levelMax)) && levelMax != 0 && levelMax <= 0xFFFF)
		backlightLevelMax = levelMax;

	// The generation may have been overridden with lilucpu, so look at the real CPU model
	auto model = BaseDeviceInfo::get().cpuModel;
	if (model != 0x8C && model != 0x8D) {
		SYSLOG("igfx", "TGLMAP: igfxtglmap ignored, CPU model 0x%X is not Tiger Lake.", model);
		return;
	}

	enabled = true;
	features = mask;
	trace = has(Log) && checkKernelArgument("-igfxtgltrace");
	PE_parse_boot_argn("igfxtglwait", &lateWait, sizeof(lateWait));
	if (has(LateState))
		publishCall = thread_call_allocate(publishThread, this);
	PE_parse_boot_argn("igfxtglcsb", &csbMode, sizeof(csbMode));
	PE_parse_boot_argn("igfxtglcsblog", &csbLog, sizeof(csbLog));
	// igfxtglcsb=1 installs the Gen12 reader; igfxtglcsblog=1 is the separate switch for the diagnostic record
	// on disk. The reader itself never writes to disk; the log is only armed when the boot argument asks for it.
	if (csbMode && csbCall == nullptr)
		csbCall = thread_call_allocate(csbThread, this);
	// (GA3.2: igfxtglhang is parsed at the top of processKernel, before the symbol resolution.)
	if (hangDump) {
		hangRec = static_cast<HangRecord *>(IOMallocAligned(sizeof(HangRecord) * HangRecord::MaxRecords, 4096));
		hangWriteBuf = static_cast<uint8_t *>(IOMallocAligned(sizeof(HangRecord) * HangRecord::MaxRecords, 4096));
		if (hangRec && hangWriteBuf) {
			bzero(hangRec, sizeof(HangRecord) * HangRecord::MaxRecords);
			hangCall = thread_call_allocate(hangThread, this);
		}
		if (!hangRec || !hangWriteBuf || !hangCall) {
			SYSLOG("igfx", "TGLMAP: hang capture disabled (record or write buffer allocation failed).");
			hangDump = 0;
		}
	}
	if (has(TraceDisk)) {
		traceCall = thread_call_allocate(traceThread, this);
		PE_parse_boot_argn("igfxtgltraceat", &traceAt, sizeof(traceAt));
	}
	keepFirmwarePLL = checkKernelArgument("-igfxtglfwpll");
	SYSLOG("igfx", "TGLMAP: Translating Ice Lake display registers for Tiger Lake (features 0x%X, fwpll %d).", features, keepFirmwarePLL);
}

bool IGFX::TigerLakeRegisterMap::shouldLog(bool isRead) {
	// IOLog may block: only when asked for, and never with interrupts disabled
	if (!has(Log) || !ml_get_interrupts_enabled())
		return false;
	if (trace)
		return true;
	auto &budget = isRead ? readLogBudget : logBudget;
	if (budget <= 0)
		return false;
	OSDecrementAtomic(&budget);
	return true;
}

uint32_t IGFX::TigerLakeRegisterMap::mapAddress(uint32_t address, bool isWrite) const {
	// eDP transcoder and its pipe configuration block -> transcoder A
	if (has(MapEdpTranscoder) && ((address >= 0x6F000 && address <= 0x6FFFF) || (address >= 0x7F000 && address <= 0x7FFFF))) {
		bool core = (address >= 0x6F000 && address <= 0x6F0FF) || (address >= 0x6F400 && address <= 0x6F41F) || (address >= 0x7F000 && address <= 0x7F0FF);
		if (has(EdpCoreOnly) && !core)
			return address;
		if (isWrite || !has(LazyEdpReads) || edpActivated)
			return address - 0xF000;
		return address;
	}
	if (has(MapDpTp)) {
		// DP_TP_CTL / DP_TP_STATUS of DDI A -> transcoder A
		if (address == 0x64040 || address == 0x64044)
			return address - 0x64040 + 0x60540;
		// DDI_DP_COMP_CTL / PAT of DDI A -> transcoder A
		if (address >= 0x640F0 && address <= 0x640FC)
			return address - 0x640F0 + 0x605F0;
	}
	// Combo DPLL configuration
	if (has(MapDpll)) {
		switch (address) {
			case 0x164000: return TGLReg::Dpll0Cfgcr0_TGL;
			case 0x164004: return TGLReg::Dpll0Cfgcr1_TGL;
			case 0x164080: return TGLReg::Dpll1Cfgcr0_TGL;
			case 0x164084: return TGLReg::Dpll1Cfgcr1_TGL;
			default: break;
		}
	}
	return address;
}

void IGFX::TigerLakeRegisterMap::record(uint32_t address, uint32_t value, bool translated) {
	auto &slot = state.ring[state.ringNext % State::RingSize];
	slot.address = address | (translated ? 0x80000000U : 0);
	slot.value = value;
	state.ringNext++;
}

void IGFX::TigerLakeRegisterMap::publish(void *controller, bool toNVRAM) {
	// Registry and NVRAM calls may block: only when asked for, and never from a context with interrupts disabled
	if (!has(PublishRegistry | PublishNVRAM) || !ml_get_interrupts_enabled())
		return;

	static const uint32_t live[] = {
		TGLReg::TransDdiFuncCtlA, TGLReg::TransClkSelA, TGLReg::TransConfA, TGLReg::DpTpCtlA_TGL, TGLReg::DpTpCtlA_TGL + 4, TGLReg::DdiBufCtlA,
		0x46010, TGLReg::Dpll0Cfgcr0_TGL, 0x46014, TGLReg::Dpll1Cfgcr0_TGL, 0x164280, 0xC7200, 0xC7204, 0xC8250
	};
	static_assert(sizeof(live) == sizeof(State::now), "live snapshot size");
	for (size_t i = 0; i < arrsize(live); i++)
		state.now[i] = callbackIGFX->modMMIORegistersReadSupport.orgReadRegister32(controller, live[i]);
	state.seq++;

	if (has(PublishRegistry))
		static_cast<IOService *>(controller)->setProperty("tgl-map-state", &state, sizeof(state));

	if (toNVRAM && has(PublishNVRAM) && nvramBudget > 0) {
		nvramBudget--;
		NVStorage storage;
		if (storage.init()) {
			storage.write(NVRAM_PREFIX(LILU_VENDOR_GUID, "tgl-map-state"), reinterpret_cast<const uint8_t *>(&state), sizeof(state), NVStorage::OptRaw);
			storage.sync();
			storage.deinit();
		}
	}
}

void IGFX::TigerLakeRegisterMap::snapshot(void *controller) {
	snapshotTaken = true;
	auto rd = callbackIGFX->modMMIORegistersReadSupport.orgReadRegister32;

	// Always needed: the firmware's transcoder A setup and the DPLL reference clock
	fwFuncCtlA = rd(controller, TGLReg::TransDdiFuncCtlA);
	refIs38400 = ((rd(controller, TGLReg::Dssm) >> 29) & 7) == 2;
	fwBacklightFreq = rd(controller, 0xC8254);
	fwBacklightDuty = rd(controller, 0xC8258);
	// The driver never writes BXT_BLC_PWM_FREQ1 when it adopts the firmware's mode without a full modeset, so its scale
	// cannot be learned from a write. AppleIntelFramebufferController::start picks it from SFUSE_STRAP bit 8:
	// 0x56CE when set, 0x4571 when clear, and hwSetBacklight computes duty = level * that / 65535.
	if (has(ScaleBacklight) && driverBacklightFreq == 0)
		driverBacklightFreq = (rd(controller, 0xC2014) & (1U << 8)) ? 0x56CE : 0x4571;
	if (has(LateState))
		takeSnapshot(controller, state.early);
	if (!has(PublishRegistry | PublishNVRAM))
		return;

	static const uint32_t regs[] = {
		TGLReg::TransDdiFuncCtlA, TGLReg::TransClkSelA, TGLReg::TransConfA, TGLReg::DpTpCtlA_TGL, TGLReg::DpTpCtlA_TGL + 4, TGLReg::DdiBufCtlA,
		0x46010, TGLReg::Dpll0Cfgcr0_TGL, TGLReg::Dpll0Cfgcr1_TGL, 0x46014, TGLReg::Dpll1Cfgcr0_TGL, TGLReg::Dpll1Cfgcr1_TGL, 0x164280, TGLReg::Dssm,
		0x60000, 0x6000C, 0x6001C, 0x45404, 0x45444, 0x45454, 0x46000
	};
	static_assert(sizeof(regs) == sizeof(State::fw), "firmware snapshot size");
	for (size_t i = 0; i < arrsize(regs); i++)
		state.fw[i] = rd(controller, regs[i]);
	publish(controller, true);
}

// Registers captured by the early and late snapshots (Tiger Lake addresses, read directly)
static const uint32_t tglSnapshotRegisters[] = {
	0x70008, 0x60400, 0x46140, 0x60540, 0x60544, 0x64000, 0x60000, 0x6000C,   // TRANS_CONF_A FUNC_CTL_A CLK_SEL_A DP_TP_CTL DP_TP_STATUS DDI_BUF_CTL HTOTAL VTOTAL
	0x6001C, 0x60030, 0x60040, 0x70030, 0x70040, 0x70000, 0x70180, 0x70188,   // PIPESRC DATAM1 LINKM1 PIPE_MISC FRMCOUNT SCANLINE PLANE_CTL_1A STRIDE
	0x7018C, 0x70190, 0x7019C, 0x7027C, 0x70240, 0x70080, 0x7017C, 0x45008,   // POS SIZE SURF PLANE_BUF_CFG PLANE_WM0 CURCNTR CUR_BUF_CFG DBUF_CTL_S1
	0x44FE8, 0x45404, 0x45504, 0x46010, 0x164284, 0x164288, 0x164280, 0xC7200, // DBUF_CTL_S2 PWR_WELL_CTL2 DC_STATE_EN DPLL0_EN CFGCR0 CFGCR1 DPCLKA PP_STATUS
	0xC7204, 0xC8250, 0xC8254, 0xC8258, 0x60800, 0x60840, 0x44400, 0x44404,   // PP_CONTROL BLC_CTL BLC_FREQ BLC_DUTY PSR_CTL PSR_STATUS DE_PIPE_ISR_A DE_PIPE_IMR_A
	0x6F400, 0x7F008, 0x68080, 0x70034, 0x4A480, 0x4A400, 0x46000, 0x70040    // (ICL eDP FUNC_CTL, CONF as TGL returns them) PF_CTL_A PIPE_MISC2 GAMMA_MODE_A CSC_MODE? CDCLK FRMCOUNT again
};

void IGFX::TigerLakeRegisterMap::takeSnapshot(void *controller, uint32_t *out) {
	static_assert(sizeof(tglSnapshotRegisters) == sizeof(State::early), "snapshot size");
	auto rd = callbackIGFX->modMMIORegistersReadSupport.orgReadRegister32;
	for (size_t i = 0; i < arrsize(tglSnapshotRegisters); i++)
		out[i] = rd(controller, tglSnapshotRegisters[i]);
}

void IGFX::TigerLakeRegisterMap::publishThread(thread_call_param_t param0, thread_call_param_t param1) {
	// Kernel thread context, no driver locks held. The record goes to a file: NVRAM writes and setProperty were
	// present in every run that reset when publishing (B, F3, F4), so neither is used here.
	auto self = static_cast<TigerLakeRegisterMap *>(param0);
	FileIO::writeBufferToFile("/Users/Shared/tgl-map-state.bin", &self->state, sizeof(self->state));
}

static uint32_t tglUptimeSeconds() {
	uint64_t t = 0, nanos = 0;
	clock_get_uptime(&t);
	absolutetime_to_nanoseconds(t, &nanos);
	return static_cast<uint32_t>(nanos / 1000000000ULL);
}

void IGFX::TigerLakeRegisterMap::traceThread(thread_call_param_t param0, thread_call_param_t) {
	// Kernel thread context. One synchronous write of the whole record at offset 0.
	auto self = static_cast<TigerLakeRegisterMap *>(param0);
	uint32_t seq = self->traceRec.seq;
	if (!self->traceContext)
		self->traceContext = vfs_context_create(nullptr);
	auto ctx = static_cast<vfs_context_t>(self->traceContext);
	if (!self->traceVnode && ctx) {
		vnode_t vp = NULLVP;
		if (vnode_open("/Users/Shared/tgl-trace.bin", O_WRONLY | O_CREAT, 0666, VNODE_LOOKUP_NOFOLLOW, &vp, ctx) == 0)
			self->traceVnode = vp;
	}
	if (self->traceVnode && ctx) {
		self->traceRec.flushes++;
		self->traceRec.nowUptime = tglUptimeSeconds();
		// The uio is not freed: uio_free is not among the symbols this kext is known to link against, and the
		// trace runs for two minutes at most.
		uio_t uio = uio_create(1, 0, UIO_SYSSPACE, UIO_WRITE);
		if (uio) {
			uio_addiov(uio, CAST_USER_ADDR_T(&self->traceRec), sizeof(self->traceRec));
			VNOP_WRITE(static_cast<vnode_t>(self->traceVnode), uio, IO_SYNC, ctx);
		}
	}
	self->traceFlushed = seq;
	// The file stays open. Closing it from here panics (vnode_close needs a process context), and an open file
	// blocks unmounting at shutdown: after a traced run, power the machine off by hand.
}

void IGFX::TigerLakeRegisterMap::traceArm(uint32_t by) {
	if (traceArmed || traceDone || !traceCall)
		return;
	traceRec.armedBy = by;
	traceRec.armUptime = tglUptimeSeconds();
	traceArmed = true;
}

void IGFX::TigerLakeRegisterMap::traceNote(uint32_t address, uint32_t value, bool isWrite) {
	if (!traceArmed) {
		if (traceAt == 0 || traceDone || !traceCall || tglUptimeSeconds() < traceAt)
			return;
		traceArm(2);
		if (!traceArmed)
			return;
	}
	if (!isWrite) {
		// Polling loops read one register thousands of times: count them in one entry, and put the entry on disk
		// when it is new and each time the count reaches a power of four, so a loop that never ends is visible.
		bool flush = true;
		if (traceRec.next != 0 && traceRec.ring[(traceRec.next - 1) % TraceRecord::RingSize].address == address) {
			uint32_t n = ++traceRec.ring[(traceRec.next - 1) % TraceRecord::RingSize].value;
			flush = n >= 4 && (n & (n - 1)) == 0 && (__builtin_ctz(n) & 1) == 0;
		} else {
			auto &slot = traceRec.ring[traceRec.next % TraceRecord::RingSize];
			slot.address = address;
			slot.value = 1;
			traceRec.next++;
		}
		if (!flush)
			return;
	} else {
		auto &slot = traceRec.ring[traceRec.next % TraceRecord::RingSize];
		slot.address = address | 0x80000000U;
		slot.value = value;
		traceRec.next++;
	}
	uint32_t seq = ++traceRec.seq;
	thread_call_enter1(traceCall, nullptr);
	// Give the writer up to 30 ms to put this access on disk before the driver carries on. No blocking calls here.
	if (!has(TraceNoWait) && ml_get_interrupts_enabled()) {
		uint32_t spins = 0;
		while (static_cast<int32_t>(traceFlushed - seq) < 0 && spins < 300) {
			IODelay(100);
			spins++;
		}
		if (spins >= 300)
			traceRec.waitTimeouts++;
	}
	if (tglUptimeSeconds() > traceRec.armUptime + 120) {
		traceArmed = false;
		traceDone = true;
	}
}

void IGFX::TigerLakeRegisterMap::lateCheck(void *controller) {
	// Called on every hooked access; cheap until the time comes.
	// Stage 1 (wait - 15 s): publish what is already in memory (the firmware snapshot), no register reads.
	// Stage 2 (wait + 15 s) and stage 3 (3 x wait): read the registers again, then publish.
	if (!has(LateState) || firstTpEnableTime == 0 || lateTaken >= 3 || !publishCall)
		return;
	uint64_t nanos = 0;
	absolutetime_to_nanoseconds(mach_absolute_time() - firstTpEnableTime, &nanos);
	uint32_t seconds = static_cast<uint32_t>(nanos / 1000000000ULL);
	uint32_t due = lateTaken == 0 ? (lateWait > 15 ? lateWait - 15 : lateWait) : lateTaken == 1 ? lateWait + 15 : lateWait * 3;
	if (seconds < due)
		return;
	if (lateTaken > 0) {
		takeSnapshot(controller, state.late);
		state.lateCount = lateTaken;
	}
	lateTaken++;
	state.lateSeconds = seconds;
	state.seq++;
	thread_call_enter1(publishCall, controller);
}

void IGFX::TigerLakeRegisterMap::prepareTranscoderA(void *controller) {
	auto rd = [&](uint32_t a) { return callbackIGFX->modMMIORegistersReadSupport.orgReadRegister32(controller, a); };
	auto wr = [&](uint32_t a, uint32_t v) { callbackIGFX->modMMIORegistersWriteSupport.orgWriteRegister32(controller, a, v); };

	// 7.a Direct the clock of DDI A to transcoder A
	uint32_t clk = rd(TGLReg::TransClkSelA);
	if (((clk >> 28) & 0xF) != 1) {
		wr(TGLReg::TransClkSelA, 1U << 28);
		state.synthClkSel++;
		record(TGLReg::TransClkSelA, 1U << 28, true);
		if (shouldLog())
			SYSLOG("igfx", "TGLMAP: TRANS_CLK_SEL_A %08X -> %08X before DP_TP_CTL enable.", clk, 1U << 28);
	}

	// 7.b DDI select, mode and lane count in TRANS_DDI_FUNC_CTL, transcoder still disabled
	uint32_t cur = rd(TGLReg::TransDdiFuncCtlA);
	if (cur & TGLReg::Enable)
		return;
	uint32_t base = lastEdpFuncCtl ? lastEdpFuncCtl : fwFuncCtlA;
	if ((base & TGLReg::ModeMask) != TGLReg::ModeDpSst)
		base = TGLReg::ModeDpSst | (rd(TGLReg::DdiBufCtlA) & TGLReg::PortWidthMask);
	uint32_t next = (base & ~TGLReg::Enable & ~(0xFU << 27)) | (1U << 27);
	if (next != cur) {
		wr(TGLReg::TransDdiFuncCtlA, next);
		state.synthFuncCtl++;
		record(TGLReg::TransDdiFuncCtlA, next, true);
		if (shouldLog())
			SYSLOG("igfx", "TGLMAP: TRANS_DDI_FUNC_CTL_A %08X -> %08X before DP_TP_CTL enable.", cur, next);
	}
}

uint32_t IGFX::TigerLakeRegisterMap::read(void *controller, uint32_t address) {
	if (!snapshotTaken)
		snapshot(controller);
	if (has(TraceDisk))
		traceNote(address, 0, false);

	uint32_t mapped = mapAddress(address, false);
	uint32_t raw = callbackIGFX->modMMIORegistersReadSupport.orgReadRegister32(controller, mapped);
	uint32_t value = raw;
	if (TGLReg::isFuncCtl(mapped) && has(XlateFuncCtl))
		value = TGLReg::funcCtlToICL(raw);
	else if (TGLReg::isClkSel(mapped) && has(XlateClkSel))
		value = TGLReg::clkSelToICL(raw);
	else if (TGLReg::isCfgcr0(mapped) && mapped != address && refIs38400)
		value = TGLReg::doubleFraction(raw);

	if (has(ScaleBacklight) && driverBacklightFreq != 0 && fwBacklightFreq != 0) {
		if (address == 0xC8254)
			value = driverBacklightFreq;
		else if (address == 0xC8258)
			value = static_cast<uint32_t>((static_cast<uint64_t>(raw) * driverDutyMax()) / fwBacklightFreq);
	}
	if (mapped != address || value != raw)
		state.mappedReads++;
	if (address == TGLReg::DpTpCtlA_ICL + 4) {
		state.lastTpStatus = raw;
		state.orTpStatus |= raw;
	}

	if ((mapped != address || value != raw) && shouldLog(true))
		SYSLOG("igfx", "TGLMAP: R %06X -> %06X = %08X (raw %08X)", address, mapped, value, raw);
	lateCheck(controller);
	return value;
}

void IGFX::TigerLakeRegisterMap::write(void *controller, uint32_t address, uint32_t value) {
	if (!snapshotTaken)
		snapshot(controller);
	if (has(TraceDisk)) {
		if (address == 0xC8258 && value == 0)
			traceArm(1);
		traceNote(address, value, true);
	}

	auto org = callbackIGFX->modMMIORegistersWriteSupport.orgWriteRegister32;
	uint32_t mapped = mapAddress(address, true);
	if (mapped != address && mapped + 0xF000 == address)
		edpActivated = true;
	uint32_t out = value;

	if (address == TGLReg::TransDdiFuncCtlEdpICL && value != 0)
		lastEdpFuncCtl = value;
	if (TGLReg::isFuncCtl(mapped)) {
		if (has(XlateFuncCtl))
			out = TGLReg::funcCtlToTGL(value);
	} else if (TGLReg::isClkSel(mapped)) {
		if (has(XlateClkSel))
			out = TGLReg::clkSelToTGL(value);
		// LightUpEDP writes TRANS_CLK_SEL(pipe) = 0 right after link training: SetupParams computes 0 for a panel on
		// DDI A because the ICL eDP transcoder has no clock select. On TGL that removes the clock of transcoder A.
		if (has(SynthPreEnable) && mapped == TGLReg::TransClkSelA && out == 0 && ddiAActive) {
			out = 1U << 28;
			state.synthClkSel++;
		}
	} else if (mapped != address && (mapped == TGLReg::Dpll0Cfgcr0_TGL || mapped == TGLReg::Dpll0Cfgcr1_TGL ||
									 mapped == TGLReg::Dpll1Cfgcr0_TGL || mapped == TGLReg::Dpll1Cfgcr1_TGL)) {
		if (keepFirmwarePLL) {
			if (shouldLog())
				SYSLOG("igfx", "TGLMAP: W %06X = %08X dropped (firmware PLL config kept).", address, value);
			return;
		}
		if (TGLReg::isCfgcr0(mapped) && refIs38400)
			out = TGLReg::halveFraction(value);
	}

	// Backlight with brightness control: the hardware keeps the firmware's PWM frequency; duty values arrive on the
	// driver's own scale and are rescaled. A zero duty is passed on: the driver writes it before it powers the panel
	// down, and holding the backlight at a high duty through that power-down freezes this machine. disableDisplay also
	// writes zero during every modeset and LightUpEDP restores only the control and frequency registers, so the last
	// level is written back when the driver switches the PWM on again.
	if (has(ScaleBacklight) && (address == 0xC8250 || address == 0xC8254 || address == 0xC8258)) {
		uint32_t out = value;
		bool restore = false;
		if (address == 0xC8250) {
			restore = backlightBlanked && (value & 0x80000000U) != 0;
		} else if (address == 0xC8254) {
			if (value != 0)
				driverBacklightFreq = value;
			out = fwBacklightFreq ? fwBacklightFreq : value;
			restore = backlightBlanked && value != 0;
		} else if (value == 0) {
			backlightBlanked = true;
		} else {
			if (driverBacklightFreq != 0 && fwBacklightFreq != 0) {
				out = static_cast<uint32_t>((static_cast<uint64_t>(value) * fwBacklightFreq) / driverDutyMax());
				if (out > fwBacklightFreq)
					out = fwBacklightFreq;
				if (out == 0)
					out = 1;
			}
			lastBacklightDuty = out;
			backlightBlanked = false;
		}
		record(address, out, true);
		state.mappedWrites++;
		if (out != 0 || address != 0xC8254)
			org(controller, address, out);
		if (restore) {
			uint32_t max = fwBacklightFreq ? fwBacklightFreq : driverBacklightFreq;
			uint32_t duty = lastBacklightDuty ? lastBacklightDuty : (fwBacklightDuty ? fwBacklightDuty : max / 2);
			lastBacklightDuty = duty;
			backlightBlanked = false;
			record(0xC8258, duty, true);
			org(controller, 0xC8258, duty);
		}
		lateCheck(controller);
		return;
	}

	// Backlight: keep what the firmware programmed. Nothing on this machine raises the duty again after the driver zeroes it.
	if (has(KeepBacklight) && (address == 0xC8254 || address == 0xC8258)) {
		uint32_t keep = address == 0xC8254 ? fwBacklightFreq : fwBacklightDuty;
		if (keep == 0 && address == 0xC8258)
			keep = fwBacklightFreq / 2;
		record(address, keep, true);
		state.mappedWrites++;
		if (keep != 0)
			org(controller, address, keep);
		lateCheck(controller);
		return;
	}

	if (address == TGLReg::DpTpCtlA_ICL)
		ddiAActive = (value & TGLReg::Enable) != 0;
	if (ddiAActive && firstTpEnableTime == 0)
		firstTpEnableTime = mach_absolute_time();
	bool tpEnable = has(SynthPreEnable) && address == TGLReg::DpTpCtlA_ICL && (value & TGLReg::Enable);
	if (tpEnable)
		prepareTranscoderA(controller);

	bool translated = mapped != address || out != value;
	if (translated)
		state.mappedWrites++;
	bool interesting = translated || (mapped >= 0x64000 && mapped <= 0x640FF) || mapped == 0x46010 || mapped == 0x46014 || mapped == 0x164280 ||
		(mapped >= 0x60000 && mapped <= 0x60FFF) || mapped == TGLReg::TransConfA || TGLReg::isClkSel(mapped) || mapped == 0xC7204;
	if (interesting)
		record(mapped, out, translated);
	if (TGLReg::isFuncCtl(mapped)) {
		state.lastFuncCtlAddr = address; state.lastFuncCtlDriver = value; state.lastFuncCtlOut = out;
	} else if (mapped == TGLReg::TransConfA) {
		state.lastConfAddr = address; state.lastConf = out;
	} else if (TGLReg::isCfgcr0(mapped)) {
		state.lastCfgcr0Addr = address; state.lastCfgcr0Driver = value; state.lastCfgcr0Out = out;
	} else if (mapped == TGLReg::Dpll0Cfgcr1_TGL || mapped == TGLReg::Dpll1Cfgcr1_TGL) {
		state.lastCfgcr1Addr = address; state.lastCfgcr1Out = out;
	} else if (mapped == TGLReg::DdiBufCtlA) {
		state.lastDdiBufCtl = out;
	} else if (mapped == 0x46010) {
		state.lastDpll0Enable = out;
	} else if (mapped == 0x46014) {
		state.lastDpll1Enable = out;
	} else if (mapped == 0x164280) {
		state.lastDpclka = out;
	} else if (TGLReg::isClkSel(mapped)) {
		state.lastClkSelOut = out;
	} else if (address == TGLReg::DpTpCtlA_ICL) {
		state.lastTpCtl = out;
		if (out & TGLReg::Enable) state.tpEnables++; else state.tpDisables++;
	}

	if ((translated || trace) && shouldLog())
		SYSLOG("igfx", "TGLMAP: W %06X -> %06X = %08X (driver %08X)", address, mapped, out, value);
	org(controller, mapped, out);

	// Publish the state when link training ends either way: pattern bits 10:8 = 3 is "normal" (trained), disable is a failure or teardown
	if (address == TGLReg::DpTpCtlA_ICL && (!(out & TGLReg::Enable) || ((out >> 8) & 7) == 3))
		publish(controller, true);

	// Port disabled. Earlier revisions cleared the DDI select in TRANS_DDI_FUNC_CTL_A and then TRANS_CLK_SEL_A here.
	// Six on-disk traces of the display-sleep freeze (with and without the DMC firmware, with the driver held back
	// and at full speed) all end right after that FUNC_CTL write, at the read of TRANS_CLK_SEL_A that followed it.
	// Nothing is touched now: the transcoder is off, and prepareTranscoderA programs both registers again before the
	// next enable.
	if (has(SynthPreEnable) && has(TraceDisk) && address == TGLReg::DpTpCtlA_ICL && !(value & TGLReg::Enable))
		traceNote(0x40000000U | 0x7, 0, true);       // marker: port disabled, no clean-up
	if (has(TraceDisk) && address == TGLReg::DpTpCtlA_ICL && !(value & TGLReg::Enable))
		traceNote(0x40000000U | 0x4, 0, true);     // marker: returning to the driver after DP_TP_CTL disable
	lateCheck(controller);
}

// MARK: - Force Complete Modeset

void IGFX::ForceCompleteModeset::init() {
	// We only need to patch the framebuffer driver
	requiresPatchingFramebuffer = true;
}

void IGFX::ForceCompleteModeset::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	uint32_t forceCompleteModeSet = 0;
	if (PE_parse_boot_argn("igfxfcms", &forceCompleteModeSet, sizeof(forceCompleteModeSet))) {
		enabled = supported && forceCompleteModeSet != 0;
		DBGLOG("weg", "force complete-modeset overriden by boot-argument %u -> %d", forceCompleteModeSet, enabled);
	} else if (WIOKit::getOSDataValue(info->videoBuiltin, "complete-modeset", forceCompleteModeSet)) {
		enabled = supported && forceCompleteModeSet != 0;
		DBGLOG("weg", "force complete-modeset overriden by device property %u -> %d", forceCompleteModeSet, enabled);
	} else if (info->firmwareVendor == DeviceInfo::FirmwareVendor::Apple) {
		enabled = false; // may interfere with FV2
		DBGLOG("weg", "force complete-modeset overriden by Apple firmware -> %d", enabled);
	}
	
	if (enabled) {
		uint64_t fbs;
		if (PE_parse_boot_argn("igfxfcmsfbs", &fbs, sizeof(fbs)) ||
			WIOKit::getOSDataValue(info->videoBuiltin, "complete-modeset-framebuffers", fbs)) {
			for (size_t i = 0; i < arrsize(this->fbs); i++)
				this->fbs[i] = (fbs >> (8 * i)) & 0xffU;
			customised = true;
		}
	}
}

void IGFX::ForceCompleteModeset::processFramebufferKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	KernelPatcher::RouteRequest request = {
		legacy ?
		"__ZN31AppleIntelFramebufferController16hwRegsNeedUpdateEP21AppleIntelFramebufferP21AppleIntelDisplayPathPNS_10CRTCParamsE" :
		"__ZN31AppleIntelFramebufferController16hwRegsNeedUpdateEP21AppleIntelFramebufferP21AppleIntelDisplayPathPNS_10CRTCParamsEPK29IODetailedTimingInformationV2",
		wrapHwRegsNeedUpdate,
		orgHwRegsNeedUpdate
	};
	
	if (!patcher.routeMultiple(index, &request, 1, address, size))
		SYSLOG("igfx", "FCM: Failed to route the function hwRegsNeedUpdate.");
}

bool IGFX::ForceCompleteModeset::wrapHwRegsNeedUpdate(void *controller, IORegistryEntry *framebuffer, void *displayPath, void *crtParams, void *detailedInfo) {
	// The framebuffer controller can perform panel fitter, partial, or a
	// complete modeset (see AppleIntelFramebufferController::hwSetMode).
	// In a dual-monitor CFL DVI+HDMI setup, only HDMI output was working after
	// boot: it was observed that for HDMI framebuffer a complete modeset
	// eventually occured, but for DVI it never did until after sleep and wake
	// sequence.
	//
	// Function AppleIntelFramebufferController::hwRegsNeedUpdate checks
	// whether a complete modeset needs to be issued. It does so by comparing
	// sets of pipes and transcoder parameters. For some reason, the result was
	// never true in the above scenario, so a complete modeset never occured.
	// Consequently, AppleIntelFramebufferController::LightUpTMDS was never
	// called for that framebuffer.
	//
	// Patching hwRegsNeedUpdate to always return true seems to be a rather
	// safe solution to that. Note that the root cause of the problem is
	// somewhere deeper.

	// On older Skylake versions this function has no detailedInfo and does not use framebuffer argument.
	// As a result the compiler does not pass framebuffer to the target function. Since the fix is disabled
	// by default for Skylake, just force complete modeset on all framebuffers when actually requested.
	if (callbackIGFX->modForceCompleteModeset.legacy)
		return true;

	// Either this framebuffer is in override list
	if (callbackIGFX->modForceCompleteModeset.customised) {
		return callbackIGFX->modForceCompleteModeset.inList(framebuffer) || callbackIGFX->modForceCompleteModeset.orgHwRegsNeedUpdate(controller, framebuffer, displayPath, crtParams, detailedInfo);
	}

	// Or it is not built-in, as indicated by AppleBacklightDisplay setting property "built-in" for
	// this framebuffer.
	// Note we need to check this at every invocation, as this property may reappear
	return !framebuffer->getProperty("built-in") || callbackIGFX->modForceCompleteModeset.orgHwRegsNeedUpdate(controller, framebuffer, displayPath, crtParams, detailedInfo);
}

// MARK: - Force Online Display

void IGFX::ForceOnlineDisplay::init() {
	// We only need to patch the framebuffer driver
	requiresPatchingFramebuffer = true;
}

void IGFX::ForceOnlineDisplay::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	uint32_t forceOnline = 0;
	if (PE_parse_boot_argn("igfxonln", &forceOnline, sizeof(forceOnline))) {
		enabled = forceOnline != 0;
		DBGLOG("weg", "force online overriden by boot-argument %u", forceOnline);
	} else if (WIOKit::getOSDataValue(info->videoBuiltin, "force-online", forceOnline)) {
		enabled = forceOnline != 0;
		DBGLOG("weg", "force online overriden by device property %u", forceOnline);
	}

	if (enabled) {
		uint64_t fbs;
		if (PE_parse_boot_argn("igfxonlnfbs", &fbs, sizeof(fbs)) ||
			WIOKit::getOSDataValue(info->videoBuiltin, "force-online-framebuffers", fbs)) {
			for (size_t i = 0; i < arrsize(this->fbs); i++)
				this->fbs[i] = (fbs >> (8 * i)) & 0xffU;
			customised = true;
		}
	}
}

void IGFX::ForceOnlineDisplay::processFramebufferKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	KernelPatcher::RouteRequest request = {
		"__ZN21AppleIntelFramebuffer16getDisplayStatusEP21AppleIntelDisplayPath",
		wrapGetDisplayStatus,
		orgGetDisplayStatus
	};
	
	if (!patcher.routeMultiple(index, &request, 1, address, size))
		SYSLOG("igfx", "FOD: Failed to route the function getDisplayStatus.");
}

uint32_t IGFX::ForceOnlineDisplay::wrapGetDisplayStatus(IORegistryEntry *framebuffer, void *displayPath) {
	// 0 - offline, 1 - online, 2 - empty dongle.
	uint32_t ret = callbackIGFX->modForceOnlineDisplay.orgGetDisplayStatus(framebuffer, displayPath);
	if (ret != 1) {
		if (callbackIGFX->modForceOnlineDisplay.customised)
			ret = callbackIGFX->modForceOnlineDisplay.inList(framebuffer) ? 1 : ret;
		else
			ret = 1;
	}

	DBGLOG("igfx", "getDisplayStatus forces %u", ret);
	return ret;
}

// MARK: - AGDC Disabler

void IGFX::AGDCDisabler::init() {
	// We only need to patch the framebuffer driver
	requiresPatchingFramebuffer = true;
}

void IGFX::AGDCDisabler::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	int agdc = info->videoBuiltin->getProperty("disable-agdc") != nullptr ? 0 : 1;
	PE_parse_boot_argn("igfxagdc", &agdc, sizeof(agdc));
	enabled = agdc == 0;
}

void IGFX::AGDCDisabler::processFramebufferKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	KernelPatcher::RouteRequest request = {
		"__ZN20IntelFBClientControl11doAttributeEjPmmS0_S0_P25IOExternalMethodArguments",
		wrapFBClientDoAttribute,
		orgFBClientDoAttribute
	};
	
	if (!patcher.routeMultiple(index, &request, 1, address, size))
		SYSLOG("igfx", "AGDCD: Failed to route the function FBClientControl::doAttribute.");
}

IOReturn IGFX::AGDCDisabler::wrapFBClientDoAttribute(void *fbclient, uint32_t attribute, unsigned long *unk1, unsigned long unk2, unsigned long *unk3, unsigned long *unk4, void *externalMethodArguments) {
	if (attribute == kAGDCRegisterCallback) {
		DBGLOG("igfx", "AGDCD: Ignoring AGDC registration in FBClientControl::doAttribute.");
		return kIOReturnUnsupported;
	}
	
	return callbackIGFX->modAGDCDisabler.orgFBClientDoAttribute(fbclient, attribute, unk1, unk2, unk3, unk4, externalMethodArguments);
}

// MARK: - Type-C Check Disabler

void IGFX::TypeCCheckDisabler::init() {
	// We only need to patch the framebuffer driver
	requiresPatchingFramebuffer = true;
}

void IGFX::TypeCCheckDisabler::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	enabled &= !checkKernelArgument("-igfxtypec");
}

void IGFX::TypeCCheckDisabler::processFramebufferKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	if (callbackIGFX->getRealFramebuffer(index) == &kextIntelCFLFb || getKernelVersion() >= KernelVersion::BigSur) {
		KernelPatcher::RouteRequest request = {
			"__ZN31AppleIntelFramebufferController17IsTypeCOnlySystemEv",
			wrapIsTypeCOnlySystem
		};
		if (!patcher.routeMultiple(index, &request, 1, address, size))
			SYSLOG("igfx", "TCCD: Failed to route the function IsTypeCOnlySystem.");
	}
}

bool IGFX::TypeCCheckDisabler::wrapIsTypeCOnlySystem(void *controller) {
	DBGLOG("igfx", "TCCD: Forcing IsTypeCOnlySystem false.");
	return false;
}

// MARK: - Black Screen Fix (HDMI/DVI Displays)

void IGFX::BlackScreenFix::init() {
	// We only need to patch the framebuffer driver
	requiresPatchingFramebuffer = true;
}

void IGFX::BlackScreenFix::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	// Black screen (ComputeLaneCount) happened from 10.12.4
	// It only affects SKL, KBL, and CFL drivers with a frame with connectors.
	if (!info->reportedFramebufferIsConnectorLess && available &&
		((getKernelVersion() == KernelVersion::Sierra && getKernelMinorVersion() >= 5) ||
		 getKernelVersion() >= KernelVersion::HighSierra)) {
		enabled = info->firmwareVendor != DeviceInfo::FirmwareVendor::Apple;
	}
}

void IGFX::BlackScreenFix::processFramebufferKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	bool foundSymbol = false;

	// Currently it is 10.14.1 and Kaby+...
	if (getKernelVersion() >= KernelVersion::Mojave &&
		BaseDeviceInfo::get().cpuGeneration >= CPUInfo::CpuGeneration::KabyLake) {
		KernelPatcher::RouteRequest request = {
			"__ZN31AppleIntelFramebufferController16ComputeLaneCountEPK29IODetailedTimingInformationV2jPj",
			wrapComputeLaneCountNouveau,
			orgComputeLaneCountNouveau
		};
		
		foundSymbol = patcher.routeMultiple(index, &request, 1, address, size);
	}

	if (!foundSymbol) {
		KernelPatcher::RouteRequest request = {
			"__ZN31AppleIntelFramebufferController16ComputeLaneCountEPK29IODetailedTimingInformationV2jjPj",
			wrapComputeLaneCount,
			orgComputeLaneCount
		};
		
		if (!patcher.routeMultiple(index, &request, 1, address, size))
			SYSLOG("igfx", "BSF: Failed to route the function ComputeLaneCount.");
	}
}

bool IGFX::BlackScreenFix::wrapComputeLaneCount(void *controller, void *detailedTiming, uint32_t bpp, int availableLanes, int *laneCount) {
	DBGLOG("igfx", "BSF: ComputeLaneCount: bpp = %u, available lanes = %d", bpp, availableLanes);

	// It seems that AGDP fails to properly detect external boot monitors. As a result computeLaneCount
	// is mistakengly called for any boot monitor (e.g. HDMI/DVI), while it is only meant to be used for
	// DP (eDP) displays. More details could be found at:
	// https://github.com/vit9696/Lilu/issues/27#issuecomment-372103559
	// Since the only problematic function is AppleIntelFramebuffer::validateDetailedTiming, there are
	// multiple ways to workaround it.
	// 1. In 10.13.4 Apple added an additional extended timing validation call, which happened to be
	// guardded by a HDMI 2.0 enable boot-arg, which resulted in one bug fixing the other, and 10.13.5
	// broke it again.
	// 2. Another good way is to intercept AppleIntelFramebufferController::RegisterAGDCCallback and
	// make sure AppleGraphicsDevicePolicy::_VendorEventHandler returns mode 2 (not 0) for event 10.
	// 3. Disabling AGDC by nopping AppleIntelFramebufferController::RegisterAGDCCallback is also fine.
	// Simply returning true from computeLaneCount and letting 0 to be compared against zero so far was
	// least destructive and most reliable. Let's stick with it until we could solve more problems.
	bool r = callbackIGFX->modBlackScreenFix.orgComputeLaneCount(controller, detailedTiming, bpp, availableLanes, laneCount);
	if (!r && *laneCount == 0) {
		DBGLOG("igfx", "BSF: Reporting worked lane count (legacy)");
		r = true;
	}

	return r;
}

bool IGFX::BlackScreenFix::wrapComputeLaneCountNouveau(void *controller, void *detailedTiming, int availableLanes, int *laneCount) {
	bool r = callbackIGFX->modBlackScreenFix.orgComputeLaneCountNouveau(controller, detailedTiming, availableLanes, laneCount);
	if (!r && *laneCount == 0) {
		DBGLOG("igfx", "reporting worked lane count (nouveau)");
		r = true;
	}

	return r;
}

// MARK: - PAVP Disabler

void IGFX::PAVPDisabler::init() {
	// We only need to patch the accelerator driver
	requiresPatchingGraphics = true;
}

void IGFX::PAVPDisabler::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	int pavpMode = info->reportedFramebufferIsConnectorLess || info->firmwareVendor == DeviceInfo::FirmwareVendor::Apple;
	if (!PE_parse_boot_argn("igfxpavp", &pavpMode, sizeof(pavpMode)))
		WIOKit::getOSDataValue(info->videoBuiltin, "igfxpavp", pavpMode);
	enabled = pavpMode == 0 && BaseDeviceInfo::get().cpuGeneration >= CPUInfo::CpuGeneration::SandyBridge;
}

void IGFX::PAVPDisabler::processGraphicsKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	const char* symbol;
	switch (BaseDeviceInfo::get().cpuGeneration) {
		case CPUInfo::CpuGeneration::SandyBridge:
			symbol = "__ZN15Gen6Accelerator19PAVPCommandCallbackE22PAVPSessionCommandID_t18PAVPSessionAppID_tPjb";
			break;
			
		case CPUInfo::CpuGeneration::IvyBridge:
			symbol = "__ZN16IntelAccelerator19PAVPCommandCallbackE22PAVPSessionCommandID_t18PAVPSessionAppID_tPjb";
			break;
			
		default:
			symbol = "__ZN16IntelAccelerator19PAVPCommandCallbackE22PAVPSessionCommandID_tjPjb";
			break;
	}

	KernelPatcher::RouteRequest request = {
		symbol,
		wrapPavpSessionCallback,
		orgPavpSessionCallback
	};
	
	if (!patcher.routeMultiple(index, &request, 1, address, size))
		SYSLOG("igfx", "PAVP: Failed to route the function PAVPCommandCallback.");
}

IOReturn IGFX::PAVPDisabler::wrapPavpSessionCallback(void *intelAccelerator, int32_t sessionCommand, uint32_t sessionAppId, uint32_t *a4, bool flag) {
	//DBGLOG("igfx, "pavpCallback: cmd = %d, flag = %d, app = %u, a4 = %s", sessionCommand, flag, sessionAppId, a4 == nullptr ? "null" : "not null");

	if (sessionCommand == 4) {
		DBGLOG("igfx", "PAVP: PavpSessionCallback: Enforcing error on cmd 4 (send to ring?)!");
		return kIOReturnTimeout; // or kIOReturnSuccess
	}

	return callbackIGFX->modPAVPDisabler.orgPavpSessionCallback(intelAccelerator, sessionCommand, sessionAppId, a4, flag);
}

// MARK: - Read Descriptors Patch

void IGFX::ReadDescriptorPatch::init() {
	// We only need to patch the accelerator driver
	requiresPatchingGraphics = true;
}

void IGFX::ReadDescriptorPatch::processKernel(KernelPatcher &patcher, DeviceInfo *info) {
	// Starting from 10.14.4b1 Skylake+ graphics randomly kernel panics on GPU usage
	enabled = BaseDeviceInfo::get().cpuGeneration >= CPUInfo::CpuGeneration::Skylake && getKernelVersion() >= KernelVersion::Mojave;
}

void IGFX::ReadDescriptorPatch::processGraphicsKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	KernelPatcher::RouteRequest request = {
		"__ZNK25IGHardwareGlobalPageTable4readEyRyS0_",
		globalPageTableRead
	};
	
	if (!patcher.routeMultiple(index, &request, 1, address, size))
		SYSLOG("igfx", "RDP: Failed to route the function IGHardwareGlobalPageTable::read.");
}

bool IGFX::ReadDescriptorPatch::globalPageTableRead(void *hardwareGlobalPageTable, uint64_t address, uint64_t &physAddress, uint64_t &flags) {
	uint64_t pageNumber = address >> PAGE_SHIFT;
	uint64_t pageEntry = getMember<uint64_t *>(hardwareGlobalPageTable, 0x28)[pageNumber];
	// PTE: Page Table Entry for 4KB Page, page 82:
	// https://01.org/sites/default/files/documentation/intel-gfx-prm-osrc-kbl-vol05-memory_views.pdf.
	physAddress = pageEntry & 0x7FFFFFF000ULL; // HAW-1:12, where HAW is 39.
	flags = pageEntry & PAGE_MASK; // 11:0
	// Relevant flag bits are as follows:
	// 2 Ignored          Ignored (h/w does not care about values behind ignored registers)
	// 1 R/W: Read/Write  Write permission rights. If 0, write permission not granted for requests with user-level privilege
	//                    (and requests with supervisor-level privilege, if WPE=1 in the relevant extended-context-entry) to
	//                    the memory region controlled by this entry. See a later section for access rights.
	//                    GPU does not support Supervisor mode contexts.
	// 0 P: Present       This bit must be “1” to point to a valid Page.
	//
	// In 10.14.4b1 the return condition changed from (flags & 7U) != 0 to (flags & 1U) != 0. The change makes good sense to me, but
	// it results in crashes on 10.14.4b1 on many ASUS Z170 and Z270 boards with connector-less IGPU framebuffer.
	// The reason for that is that __ZNK31IGHardwarePerProcessPageTable6422readDescriptorForRangeERK14IGAddressRangePPN10IGPagePool14PageDescriptorE
	// unconditionally returns true but actually returns NULL PageDescriptor, which subsequently results in OSAddAtomic64(&this->counter)
	// __ZN31IGHardwarePerProcessPageTable6421mapDescriptorForRangeERK14IGAddressRangePN10IGPagePool14PageDescriptorE writing to invalid address.
	//
	// Fault CR2: 0x0000000000000028, Error code: 0x0000000000000002, Fault CPU: 0x1, PL: 0, VF: 0
	// 0xffffff821885b8f0 : 0xffffff801d3c7dc4 mach_kernel : _OSAddAtomic64 + 0x4
	// 0xffffff821885b9e0 : 0xffffff7f9f3f1845 com.apple.driver.AppleIntelKBLGraphics :
	//                      __ZN31IGHardwarePerProcessPageTable6421mapDescriptorForRangeERK14IGAddressRangePN10IGPagePool14PageDescriptorE + 0x6b
	// 0xffffff821885ba20 : 0xffffff7f9f40a3c3 com.apple.driver.AppleIntelKBLGraphics :
	//                      __ZN29IGHardwarePerProcessPageTable25synchronizePageDescriptorEPKS_RK14IGAddressRangeb + 0x51
	// 0xffffff821885ba50 : 0xffffff7f9f40a36b com.apple.driver.AppleIntelKBLGraphics :
	//                      __ZN29IGHardwarePerProcessPageTable15synchronizeWithIS_EEvPKT_RK14IGAddressRangeb + 0x37
	// 0xffffff821885ba70 : 0xffffff7f9f3b1716 com.apple.driver.AppleIntelKBLGraphics : __ZN15IGMemoryManager19newPageTableForTaskEP11IGAccelTask + 0x98
	// 0xffffff821885baa0 : 0xffffff7f9f40a716 com.apple.driver.AppleIntelKBLGraphics : __ZN11IGAccelTask15initWithOptionsEP16IntelAccelerator + 0x108
	// 0xffffff821885bad0 : 0xffffff7f9f40a5f7 com.apple.driver.AppleIntelKBLGraphics : __ZN11IGAccelTask11withOptionsEP16IntelAccelerator + 0x31
	// 0xffffff821885baf0 : 0xffffff7f9f3bfaf0 com.apple.driver.AppleIntelKBLGraphics : __ZN16IntelAccelerator17createUserGPUTaskEv + 0x30
	// 0xffffff821885bb10 : 0xffffff7f9f2f7520 com.apple.iokit.IOAcceleratorFamily2 : __ZN14IOAccelShared24initEP22IOGraphicsAccelerator2P4task + 0x2e
	// 0xffffff821885bb50 : 0xffffff7f9f30c157 com.apple.iokit.IOAcceleratorFamily2 : __ZN22IOGraphicsAccelerator212createSharedEP4task + 0x33
	// 0xffffff821885bb80 : 0xffffff7f9f2faa95 com.apple.iokit.IOAcceleratorFamily2 : __ZN24IOAccelSharedUserClient211sharedStartEv + 0x2b
	// 0xffffff821885bba0 : 0xffffff7f9f401ca2 com.apple.driver.AppleIntelKBLGraphics : __ZN23IGAccelSharedUserClient11sharedStartEv + 0x16
	// 0xffffff821885bbc0 : 0xffffff7f9f2f8aaa com.apple.iokit.IOAcceleratorFamily2 : __ZN24IOAccelSharedUserClient25startEP9IOService + 0x9c
	// 0xffffff821885bbf0 : 0xffffff7f9f30ba3c com.apple.iokit.IOAcceleratorFamily2 : __ZN22IOGraphicsAccelerator213newUserClientEP4taskPvjPP12IOUserClient + 0x43e
	// 0xffffff821885bc80 : 0xffffff801d42a040 mach_kernel : __ZN9IOService13newUserClientEP4taskPvjP12OSDictionaryPP12IOUserClient + 0x30
	// 0xffffff821885bcd0 : 0xffffff801d48ef9a mach_kernel : _is_io_service_open_extended + 0x10a
	// 0xffffff821885bd30 : 0xffffff801ce96b52 mach_kernel : _iokit_server_routine + 0x58d2
	// 0xffffff821885bd80 : 0xffffff801cdb506c mach_kernel : _ipc_kobject_server + 0x12c
	// 0xffffff821885bdd0 : 0xffffff801cd8fa91 mach_kernel : _ipc_kmsg_send + 0xd1
	// 0xffffff821885be50 : 0xffffff801cda42fe mach_kernel : _mach_msg_overwrite_trap + 0x3ce
	// 0xffffff821885bef0 : 0xffffff801cec3e87 mach_kernel : _mach_call_munger64 + 0x257
	// 0xffffff821885bfa0 : 0xffffff801cd5d2c6 mach_kernel : _hndl_mach_scall64 + 0x16
	//
	// Even so the change makes good sense to me, and most likely the real bug is elsewhere. The change workarounds the issue by also checking
	// for the W (writeable) bit in addition to P (present). Presumably this works because some code misuses ::read method to iterate
	// over page table instead of obtaining valid mapped physical address.
	return (flags & 3U) != 0;
}

// MARK: - TODO

OSObject *IGFX::wrapCopyExistingServices(OSDictionary *matching, IOOptionBits inState, IOOptionBits options) {
	if (matching && inState == kIOServiceMatchedState && options == 0) {
		auto name = OSDynamicCast(OSString, matching->getObject(gIONameMatchKey));
		if (name) {
			DBGLOG("igfx", "found matching request by name %s", name->getCStringNoCopy());
			if (name->isEqualTo("Gen6Accelerator")) {
				DBGLOG("igfx", "found and fixed Gen6Accelerator request");
				auto accel = OSString::withCString("IntelAccelerator");
				if (accel) {
					matching->setObject(gIONameMatchKey, accel);
					accel->release();
				}
			}
		}
	}

	return FunctionCast(wrapCopyExistingServices, callbackIGFX->orgCopyExistingServices)(matching, inState, options);
}

bool IGFX::applyDevelopmentPatches(IOService *that) {
	// skip if not requested
	if (callbackIGFX->fwLoadMode == FW_APPLE && !callbackIGFX->modForceWakeWorkaround.enabled) {
		return true;
	}

	auto devDict = OSDynamicCast(OSDictionary, that->getProperty("Development"));
	if (!devDict)
		return false;

	auto newDevDict = OSDictionary::withDictionary(devDict);
	if (!newDevDict)
		return false;

	// By default Apple drivers load Apple-specific firmware, which is incompatible.
	// On KBL they do it unconditionally, which causes infinite loop.
	// On 10.13 there is an option to ignore/load a generic firmware, which we set here.
	// On 10.12 it is not necessary.
	// On 10.15 an option is differently named but still there.
	// There are some laptops that support Apple firmware, for them we want it to be loaded explicitly.
	// REF: https://github.com/acidanthera/bugtracker/issues/748
	if (callbackIGFX->fwLoadMode != FW_APPLE) {
		// 1 - Automatic scheduler (Apple -> fallback to disabled)
		// 2 - Force disable via plist (removed as of 10.15)
		// 3 - Apple Scheduler
		// 4 - Reference Scheduler
		// 5 - Host Preemptive (as of 10.15)
		uint32_t scheduler;
		if (callbackIGFX->fwLoadMode == FW_GENERIC)
			scheduler = 4;
		else if (getKernelVersion() >= KernelVersion::Catalina)
			scheduler = 5;
		else
			scheduler = 2;
		auto num = OSNumber::withNumber(scheduler, 32);
		if (num) {
			newDevDict->setObject("GraphicsSchedulerSelect", num);
			num->release();
		}
	}

	// 0: Framebuffer's SafeForceWake
	// 1: IntelAccelerator::SafeForceWakeMultithreaded (or ForceWakeWorkaround when enabled)
	// The default is 1. Forcing 0 will result in hangs (due to misbalanced number of calls?)
	if (callbackIGFX->modForceWakeWorkaround.enabled) {
		auto num = OSNumber::withNumber(1ull, 32);
		if (num) {
			newDevDict->setObject("MultiForceWakeSelect", num);
			num->release();
		}
	}

	that->setProperty("Development", newDevDict);
	newDevDict->release();

	return true;
}

bool IGFX::applySklAsKblPatches(IOService *that) {
	DBGLOG("igfx", "disabling VP9 hw decode support on Skylake with KBL kexts");
	that->removeProperty("IOGVAXDecode");

	// SKL does not support 10-bit hardware encoding/decoding, and this causes freezing when attempting to do so.
	// The removal of profile 2 under VTSupportedProfileArray allows fallback to software encoding/decoding.
	// Thanks dhinakg and aben for finding this.
	const char *hevcCapProps[] = { "IOGVAHEVCDecodeCapabilities", "IOGVAHEVCEncodeCapabilities" };
	bool found = false;
	for (auto prop : hevcCapProps) {
		auto hevcCap = OSDynamicCast(OSDictionary, that->getProperty(prop));
		if (!hevcCap)
			continue;

		auto newHevcCap = OSDictionary::withDictionary(hevcCap);
		if (!newHevcCap)
			continue;

		auto vtSuppProf = OSDynamicCast(OSArray, newHevcCap->getObject("VTSupportedProfileArray"));
		if (!vtSuppProf) {
			newHevcCap->release();
			continue;
		}

		auto newVtSuppProf = OSArray::withArray(vtSuppProf);
		if (!newVtSuppProf) {
			newHevcCap->release();
			continue;
		}

		unsigned int count = newVtSuppProf->getCount();
		for (unsigned int i = 0; i < count; i++) {
			auto num = OSDynamicCast(OSNumber, newVtSuppProf->getObject(i));
			if (!num)
				continue;

			if (num->unsigned8BitValue() == 2) {
				DBGLOG("igfx", "removing profile 2 from VTSupportedProfileArray/%s index %u on Skylake with KBL kexts", prop, i);
				newVtSuppProf->removeObject(i);
				found = true;
				break;
			}
		}

		newHevcCap->setObject("VTSupportedProfileArray", newVtSuppProf);
		newVtSuppProf->release();

		that->setProperty(prop, newHevcCap);
		newHevcCap->release();
	}

	// NOTE: The patches/overriding above may not be sufficient.
	//       `AAPL,GfxYTile` with value `01` may be injected for the glitch fix.
	// Ref: https://github.com/acidanthera/bugtracker/issues/2088#issuecomment-1381357651

	return found;
}

bool IGFX::wrapAcceleratorStart(IOService *that, IOService *provider) {
	if (callbackIGFX->disableAccel)
		return false;
	
	if (!applyDevelopmentPatches(that))
		SYSLOG("igfx", "failed to apply dict Development patches");

	OSObject *metalPluginName = that->getProperty("MetalPluginName");
	if (metalPluginName) {
		metalPluginName->retain();
	}

	if (callbackIGFX->forceOpenGL) {
		DBGLOG("igfx", "disabling metal support");
		that->removeProperty("MetalPluginClassName");
		that->removeProperty("MetalPluginName");
		that->removeProperty("MetalStatisticsName");
	}

	if (callbackIGFX->moderniseAccelerator)
		that->setName("IntelAccelerator");
	
	if (callbackIGFX->forceSKLAsKBL && !applySklAsKblPatches(that)) {
		SYSLOG("igfx", "failed to apply patches for Skylake with KBL kexts");
	}

	bool ret = FunctionCast(wrapAcceleratorStart, callbackIGFX->orgAcceleratorStart)(that, provider);

	if (metalPluginName) {
		if (callbackIGFX->forceMetal) {
			DBGLOG("igfx", "enabling metal support");
			that->setProperty("MetalPluginName", metalPluginName);
		}
		metalPluginName->release();
	}

	return ret;
}

bool IGFX::wrapGetOSInformation(IOService *that) {
	auto cpuGeneration = BaseDeviceInfo::get().cpuGeneration;
	
#ifdef DEBUG
	if (callbackIGFX->dumpFramebufferToDisk) {
		char name[64];
		snprintf(name, sizeof(name), "/var/log/AppleIntelFramebuffer_%d_%d.%d", cpuGeneration, getKernelVersion(), getKernelMinorVersion());
		FileIO::writeBufferToFile(name, callbackIGFX->framebufferStart, callbackIGFX->framebufferSize);
		SYSLOG("igfx", "dumping framebuffer information to %s", name);
		uint32_t delay = 20000;
		PE_parse_boot_argn("igfxdumpdelay", &delay, sizeof(delay));
		IOSleep(delay);
	}
#endif

#ifdef DEBUG
	if (callbackIGFX->dumpPlatformTable)
		callbackIGFX->writePlatformListData("platform-table-native");
#endif

	if (callbackIGFX->applyFramebufferPatch && cpuGeneration >= CPUInfo::CpuGeneration::SandyBridge)
		callbackIGFX->applyFramebufferPatches();
	else if (callbackIGFX->applyFramebufferPatch && cpuGeneration == CPUInfo::CpuGeneration::Westmere)
		callbackIGFX->applyWestmereFeaturePatches(that);
	else if (callbackIGFX->hdmiAutopatch)
		callbackIGFX->applyHdmiAutopatch();

#ifdef DEBUG
	if (callbackIGFX->dumpPlatformTable)
		callbackIGFX->writePlatformListData("platform-table-patched");
#endif

	return FunctionCast(wrapGetOSInformation, callbackIGFX->orgGetOSInformation)(that);
}

bool IGFX::wrapLoadGuCBinary(void *that, bool flag) {
	bool r = false;
	DBGLOG("igfx", "attempting to load firmware for %d scheduler for cpu gen %d",
		   callbackIGFX->fwLoadMode, BaseDeviceInfo::get().cpuGeneration);

	if (callbackIGFX->firmwareSizePointer)
		callbackIGFX->performingFirmwareLoad = true;

	r = FunctionCast(wrapLoadGuCBinary, callbackIGFX->orgLoadGuCBinary)(that, flag);
	DBGLOG("igfx", "loadGuCBinary returned %d", r);

	callbackIGFX->performingFirmwareLoad = false;

	return r;
}

bool IGFX::wrapLoadFirmware(IOService *that) {
	DBGLOG("igfx", "load firmware setting sleep overrides %d", BaseDeviceInfo::get().cpuGeneration);

	// We have to patch the virtual table, because the original methods are very short.
	// See __ZN12IGScheduler415systemWillSleepEv and __ZN12IGScheduler413systemDidWakeEv
	// Note, that other methods are also not really implemented, so we may have to implement them ourselves sooner or later.
	(*reinterpret_cast<uintptr_t **>(that))[52] = reinterpret_cast<uintptr_t>(wrapSystemWillSleep);
	(*reinterpret_cast<uintptr_t **>(that))[53] = reinterpret_cast<uintptr_t>(wrapSystemDidWake);
	return FunctionCast(wrapLoadFirmware, callbackIGFX->orgLoadFirmware)(that);
}

void IGFX::wrapSystemWillSleep(IOService *that) {
	DBGLOG("igfx", "systemWillSleep GuC callback");
	// Perhaps we want to send a message to GuC firmware like Apple does for its own implementation?
}

void IGFX::wrapSystemDidWake(IOService *that) {
	DBGLOG("igfx", "systemDidWake GuC callback");

	// This is IGHardwareGuC class instance.
	auto &GuC = (reinterpret_cast<OSObject **>(that))[76];
	DBGLOG("igfx", "reloading firmware on wake discovered IGHardwareGuC %d", GuC != nullptr);
	if (GuC) {
		GuC->release();
		GuC = nullptr;
	}

	FunctionCast(wrapLoadFirmware, callbackIGFX->orgLoadFirmware)(that);
}

bool IGFX::wrapInitSchedControl(void *that, void *ctrl) {
	// This function is caled within loadGuCBinary, and it also uses shared buffers.
	// To avoid any issues here we ensure that the filtering is off.
	DBGLOG("igfx", "attempting to init sched control with load %d", callbackIGFX->performingFirmwareLoad);
	bool perfLoad = callbackIGFX->performingFirmwareLoad;
	callbackIGFX->performingFirmwareLoad = false;
	bool r = FunctionCast(wrapInitSchedControl, callbackIGFX->orgInitSchedControl)(that, ctrl);

#ifdef DEBUG
	if (callbackIGFX->fwLoadMode == FW_GENERIC) {
		struct ParamRegs {
			uint32_t bak[35];
			uint32_t params[10];
		};

		auto v = &static_cast<ParamRegs *>(that)->params[0];
		DBGLOG("igfx", "fw params1 %08X %08X %08X %08X %08X", v[0], v[1], v[2], v[3], v[4]);
		DBGLOG("igfx", "fw params2 %08X %08X %08X %08X %08X", v[5], v[6], v[7], v[8], v[9]);
	}
#endif

	callbackIGFX->performingFirmwareLoad = perfLoad;
	return r;
}

void *IGFX::wrapIgBufferWithOptions(void *accelTask, unsigned long size, unsigned int type, unsigned int flags) {
	auto cpuGeneration = BaseDeviceInfo::get().cpuGeneration;
	void *r = nullptr;

	if (callbackIGFX->performingFirmwareLoad) {
		// Allocate a dummy buffer
		callbackIGFX->dummyFirmwareBuffer = Buffer::create<uint8_t>(size);
		// Select the latest firmware to upload
		DBGLOG("igfx", "preparing firmware for cpu gen %d with range 0x%lX", cpuGeneration, size);

		const void *fw = nullptr;
		const void *fwsig = nullptr;
		size_t fwsize = 0;
		size_t fwsigsize = 0;

		if (cpuGeneration == CPUInfo::CpuGeneration::Skylake) {
			fw = GuCFirmwareSKL;
			fwsig = GuCFirmwareSKLSignature;
			fwsize = GuCFirmwareSKLSize;
			fwsigsize = GuCFirmwareSignatureSize;
		} else {
			fw = GuCFirmwareKBL;
			fwsig = GuCFirmwareKBLSignature;
			fwsize = GuCFirmwareKBLSize;
			fwsigsize = GuCFirmwareSignatureSize;
		}

		// Allocate enough memory for the new firmware (should be 64K-aligned)
		unsigned long newsize = fwsize > size ? ((fwsize + 0xFFFF) & (~0xFFFF)) : size;
		r = FunctionCast(wrapIgBufferWithOptions, callbackIGFX->orgIgBufferWithOptions)(accelTask, newsize, type, flags);
		// Replace the real buffer with a dummy buffer
		if (r && callbackIGFX->dummyFirmwareBuffer) {
			// Copy firmware contents, update the sizes and signature
			auto status = MachInfo::setKernelWriting(true, KernelPatcher::kernelWriteLock);
			if (status == KERN_SUCCESS) {
				// Upload the firmware ourselves
				callbackIGFX->realFirmwareBuffer = static_cast<uint8_t **>(r)[7];
				static_cast<uint8_t **>(r)[7] = callbackIGFX->dummyFirmwareBuffer;
				lilu_os_memcpy(callbackIGFX->realFirmwareBuffer, fw, fwsize);
				lilu_os_memcpy(callbackIGFX->signaturePointer, fwsig, fwsigsize);
				callbackIGFX->realBinarySize = static_cast<uint32_t>(fwsize);
				// Update the firmware size for IGScheduler4
				*callbackIGFX->firmwareSizePointer = static_cast<uint32_t>(fwsize);
				MachInfo::setKernelWriting(false, KernelPatcher::kernelWriteLock);
			} else {
				SYSLOG("igfx", "ig buffer protection upgrade failure %d", status);
			}
		} else if (callbackIGFX->dummyFirmwareBuffer) {
			SYSLOG("igfx", "ig shared buffer allocation failure");
			Buffer::deleter(callbackIGFX->dummyFirmwareBuffer);
			callbackIGFX->dummyFirmwareBuffer = nullptr;
		} else {
			SYSLOG("igfx", "dummy buffer allocation failure");
		}
	} else {
		r = FunctionCast(wrapIgBufferWithOptions, callbackIGFX->orgIgBufferWithOptions)(accelTask, size, type, flags);
	}

	return r;
}

uint64_t IGFX::wrapIgBufferGetGpuVirtualAddress(void *that) {
	if (callbackIGFX->performingFirmwareLoad && callbackIGFX->realFirmwareBuffer) {
		// Restore the original firmware buffer
		static_cast<uint8_t **>(that)[7] = callbackIGFX->realFirmwareBuffer;
		callbackIGFX->realFirmwareBuffer = nullptr;
		// Free the dummy framebuffer which is no longer used
		Buffer::deleter(callbackIGFX->dummyFirmwareBuffer);
		callbackIGFX->dummyFirmwareBuffer = nullptr;
	}

	return FunctionCast(wrapIgBufferGetGpuVirtualAddress, callbackIGFX->orgIgBufferGetGpuVirtualAddress)(that);
}

void IGFX::loadIGScheduler4Patches(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
	gKmGen9GuCBinary = patcher.solveSymbol<uint8_t *>(index, "__ZL17__KmGen9GuCBinary", address, size);
	if (gKmGen9GuCBinary) {
		DBGLOG("igfx", "obtained __KmGen9GuCBinary");

		auto loadGuC = patcher.solveSymbol(index, "__ZN13IGHardwareGuC13loadGuCBinaryEv", address, size);
		if (loadGuC) {
			DBGLOG("igfx", "obtained IGHardwareGuC::loadGuCBinary");

			// Lookup the assignment to the size register.
			uint8_t sizeReg[] {0x10, 0xC3, 0x00, 0x00};
			auto pos    = reinterpret_cast<uint8_t *>(loadGuC);
			auto endPos = pos + PAGE_SIZE;
			while (memcmp(pos, sizeReg, sizeof(sizeReg)) != 0 && pos < endPos)
				pos++;

			// Verify and store the size pointer
			if (pos != endPos) {
				pos += sizeof(uint32_t);
				firmwareSizePointer = reinterpret_cast<uint32_t *>(pos);
				DBGLOG("igfx", "discovered firmware size: %u bytes", *firmwareSizePointer);
				// Firmware size must not be bigger than 1 MB
				if ((*firmwareSizePointer & 0xFFFFF) == *firmwareSizePointer)
					// Firmware follows the signature
					signaturePointer = gKmGen9GuCBinary + *firmwareSizePointer;
				else
					firmwareSizePointer = nullptr;
			}

			if (firmwareSizePointer) {
				orgLoadGuCBinary = patcher.routeFunction(loadGuC, reinterpret_cast<mach_vm_address_t>(wrapLoadGuCBinary), true);
				if (patcher.getError() == KernelPatcher::Error::NoError) {
					DBGLOG("igfx", "routed IGHardwareGuC::loadGuCBinary");

					KernelPatcher::RouteRequest requests[] {
						{"__ZN12IGScheduler412loadFirmwareEv", wrapLoadFirmware, orgLoadFirmware},
						{"__ZN13IGHardwareGuC16initSchedControlEv", wrapInitSchedControl, orgInitSchedControl},
						{"__ZN20IGSharedMappedBuffer11withOptionsEP11IGAccelTaskmjj", wrapIgBufferWithOptions, orgIgBufferWithOptions},
						{"__ZNK14IGMappedBuffer20getGPUVirtualAddressEv", wrapIgBufferGetGpuVirtualAddress, orgIgBufferGetGpuVirtualAddress},
					};
					patcher.routeMultiple(index, requests, address, size);
				} else {
					SYSLOG("igfx", "failed to route IGHardwareGuC::loadGuCBinary %d", patcher.getError());
					patcher.clearError();
				}
			} else {
				SYSLOG("igfx", "failed to find GuC firmware size assignment");
			}
		} else {
			SYSLOG("igfx", "failed to resolve IGHardwareGuC::loadGuCBinary %d", patcher.getError());
			patcher.clearError();
		}
	} else {
		SYSLOG("igfx", "failed to resolve __KmGen9GuCBinary %d", patcher.getError());
		patcher.clearError();
	}
}

bool IGFX::loadPatchesFromDevice(IORegistryEntry *igpu, uint32_t currentFramebufferId) {
	bool hasFramebufferPatch = false;
	
	auto cpuGeneration = BaseDeviceInfo::get().cpuGeneration;

	uint32_t framebufferPatchEnable = 0;
	if (WIOKit::getOSDataValue(igpu, "framebuffer-patch-enable", framebufferPatchEnable) && framebufferPatchEnable) {
		DBGLOG("igfx", "framebuffer-patch-enable %d", framebufferPatchEnable);
		
		if (cpuGeneration == CPUInfo::CpuGeneration::Westmere) {
			hasFramebufferPatch = true;
			
			// First generation only has link mode and width patching.
			framebufferPatchFlags.bitsWestmere.LinkWidth = WIOKit::getOSDataValue(igpu, "framebuffer-linkwidth", framebufferWestmerePatches.LinkWidth);
			framebufferPatchFlags.bitsWestmere.SingleLink = WIOKit::getOSDataValue(igpu, "framebuffer-singlelink", framebufferWestmerePatches.SingleLink);
			
			framebufferPatchFlags.bitsWestmere.FBCControlCompression =
				WIOKit::getOSDataValue(igpu, "framebuffer-fbccontrol-compression", framebufferWestmerePatches.FBCControlCompression);
			framebufferPatchFlags.bitsWestmere.FeatureControlFBC =
				WIOKit::getOSDataValue(igpu, "framebuffer-featurecontrol-fbc", framebufferWestmerePatches.FeatureControlFBC);
			framebufferPatchFlags.bitsWestmere.FeatureControlGPUInterruptHandling =
				WIOKit::getOSDataValue(igpu, "framebuffer-featurecontrol-gpuinterrupthandling", framebufferWestmerePatches.FeatureControlGPUInterruptHandling);
			framebufferPatchFlags.bitsWestmere.FeatureControlGamma =
				WIOKit::getOSDataValue(igpu, "framebuffer-featurecontrol-gamma", framebufferWestmerePatches.FeatureControlGamma);
			framebufferPatchFlags.bitsWestmere.FeatureControlMaximumSelfRefreshLevel =
				WIOKit::getOSDataValue(igpu, "framebuffer-featurecontrol-maximumselfrefreshlevel", framebufferWestmerePatches.FeatureControlMaximumSelfRefreshLevel);
			framebufferPatchFlags.bitsWestmere.FeatureControlPowerStates =
				WIOKit::getOSDataValue(igpu, "framebuffer-featurecontrol-powerstates", framebufferWestmerePatches.FeatureControlPowerStates);
			framebufferPatchFlags.bitsWestmere.FeatureControlRSTimerTest =
				WIOKit::getOSDataValue(igpu, "framebuffer-featurecontrol-rstimertest", framebufferWestmerePatches.FeatureControlRSTimerTest);
			framebufferPatchFlags.bitsWestmere.FeatureControlRenderStandby =
				WIOKit::getOSDataValue(igpu, "framebuffer-featurecontrol-renderstandby", framebufferWestmerePatches.FeatureControlRenderStandby);
			framebufferPatchFlags.bitsWestmere.FeatureControlWatermarks =
				WIOKit::getOSDataValue(igpu, "framebuffer-featurecontrol-watermarks", framebufferWestmerePatches.FeatureControlWatermarks);
			
			// Settings above will override all-zero settings.
			uint32_t fbcControlAllZero = 0;
			if (WIOKit::getOSDataValue(igpu, "framebuffer-fbccontrol-allzero", fbcControlAllZero) && fbcControlAllZero) {
				framebufferPatchFlags.bitsWestmere.FBCControlCompression = 1;
			}
			
			// Settings above will override all-zero settings.
			uint32_t featureControlAllZero = 0;
			if (WIOKit::getOSDataValue(igpu, "framebuffer-featurecontrol-allzero", featureControlAllZero) && featureControlAllZero) {
				framebufferPatchFlags.bitsWestmere.FeatureControlFBC = 1;
				framebufferPatchFlags.bitsWestmere.FeatureControlGPUInterruptHandling = 1;
				framebufferPatchFlags.bitsWestmere.FeatureControlGamma = 1;
				framebufferPatchFlags.bitsWestmere.FeatureControlMaximumSelfRefreshLevel = 1;
				framebufferPatchFlags.bitsWestmere.FeatureControlPowerStates = 1;
				framebufferPatchFlags.bitsWestmere.FeatureControlRSTimerTest = 1;
				framebufferPatchFlags.bitsWestmere.FeatureControlRenderStandby = 1;
				framebufferPatchFlags.bitsWestmere.FeatureControlWatermarks = 1;
			}
		} else if (cpuGeneration >= CPUInfo::CpuGeneration::SandyBridge) {
			// Note, the casts to uint32_t here and below are required due to device properties always injecting 32-bit types.
			framebufferPatchFlags.bits.FPFFramebufferId = WIOKit::getOSDataValue(igpu, "framebuffer-framebufferid", framebufferPatch.framebufferId);
			framebufferPatchFlags.bits.FPFFlags = WIOKit::getOSDataValue(igpu, "framebuffer-flags", framebufferPatch.flags.value);
			framebufferPatchFlags.bits.FPFCamelliaVersion = WIOKit::getOSDataValue(igpu, "framebuffer-camellia", framebufferPatch.camelliaVersion);
			framebufferPatchFlags.bits.FPFMobile = WIOKit::getOSDataValue<uint32_t>(igpu, "framebuffer-mobile", framebufferPatch.fMobile);
			framebufferPatchFlags.bits.FPFPipeCount = WIOKit::getOSDataValue<uint32_t>(igpu, "framebuffer-pipecount", framebufferPatch.fPipeCount);
			framebufferPatchFlags.bits.FPFPortCount = WIOKit::getOSDataValue<uint32_t>(igpu, "framebuffer-portcount", framebufferPatch.fPortCount);
			framebufferPatchFlags.bits.FPFFBMemoryCount = WIOKit::getOSDataValue<uint32_t>(igpu, "framebuffer-memorycount", framebufferPatch.fFBMemoryCount);
			framebufferPatchFlags.bits.FPFStolenMemorySize = WIOKit::getOSDataValue(igpu, "framebuffer-stolenmem", framebufferPatch.fStolenMemorySize);
			framebufferPatchFlags.bits.FPFFramebufferMemorySize = WIOKit::getOSDataValue(igpu, "framebuffer-fbmem", framebufferPatch.fFramebufferMemorySize);
			framebufferPatchFlags.bits.FPFUnifiedMemorySize = WIOKit::getOSDataValue(igpu, "framebuffer-unifiedmem", framebufferPatch.fUnifiedMemorySize);
			framebufferPatchFlags.bits.FPFFramebufferCursorSize = WIOKit::getOSDataValue(igpu, "framebuffer-cursormem", fPatchCursorMemorySize);

			if (framebufferPatchFlags.value != 0)
				hasFramebufferPatch = true;

			for (size_t i = 0; i < arrsize(framebufferPatch.connectors); i++) {
				char name[48];
				snprintf(name, sizeof(name), "framebuffer-con%lu-enable", i);
				uint32_t framebufferConnectorPatchEnable = 0;
				if (!WIOKit::getOSDataValue(igpu, name, framebufferConnectorPatchEnable) || !framebufferConnectorPatchEnable)
					continue;

				DBGLOG("igfx", "framebuffer-con%lu-enable %d", i, framebufferConnectorPatchEnable);

				snprintf(name, sizeof(name), "framebuffer-con%lu-%08x-alldata", i, currentFramebufferId);
				auto allData = OSDynamicCast(OSData, igpu->getProperty(name));
				if (!allData) {
					snprintf(name, sizeof(name), "framebuffer-con%lu-alldata", i);
					allData = OSDynamicCast(OSData, igpu->getProperty(name));
				}
				if (allData) {
					auto allDataSize = allData->getLength();
					auto replaceCount = allDataSize / sizeof(ConnectorInfo);
					if (0 == allDataSize % sizeof(ConnectorInfo) && i + replaceCount <= arrsize(framebufferPatch.connectors)) {
						auto replacementConnectors = reinterpret_cast<const ConnectorInfo*>(allData->getBytesNoCopy());
						for (size_t j = 0; j < replaceCount; j++) {
							framebufferPatch.connectors[i+j].index = replacementConnectors[j].index;
							framebufferPatch.connectors[i+j].busId = replacementConnectors[j].busId;
							framebufferPatch.connectors[i+j].pipe = replacementConnectors[j].pipe;
							framebufferPatch.connectors[i+j].pad = replacementConnectors[j].pad;
							framebufferPatch.connectors[i+j].type = replacementConnectors[j].type;
							framebufferPatch.connectors[i+j].flags = replacementConnectors[j].flags;
							connectorPatchFlags[i+j].bits.CPFIndex = true;
							connectorPatchFlags[i+j].bits.CPFBusId = true;
							connectorPatchFlags[i+j].bits.CPFPipe = true;
							connectorPatchFlags[i+j].bits.CPFType = true;
							connectorPatchFlags[i+j].bits.CPFFlags = true;
						}
					}
				}

				snprintf(name, sizeof(name), "framebuffer-con%lu-index", i);
				connectorPatchFlags[i].bits.CPFIndex |= WIOKit::getOSDataValue(igpu, name, framebufferPatch.connectors[i].index);
				snprintf(name, sizeof(name), "framebuffer-con%lu-busid", i);
				connectorPatchFlags[i].bits.CPFBusId |= WIOKit::getOSDataValue(igpu, name, framebufferPatch.connectors[i].busId);
				snprintf(name, sizeof(name), "framebuffer-con%lu-pipe", i);
				connectorPatchFlags[i].bits.CPFPipe |= WIOKit::getOSDataValue(igpu, name, framebufferPatch.connectors[i].pipe);
				snprintf(name, sizeof(name), "framebuffer-con%lu-type", i);
				connectorPatchFlags[i].bits.CPFType |= WIOKit::getOSDataValue(igpu, name, framebufferPatch.connectors[i].type);
				snprintf(name, sizeof(name), "framebuffer-con%lu-flags", i);
				connectorPatchFlags[i].bits.CPFFlags |= WIOKit::getOSDataValue(igpu, name, framebufferPatch.connectors[i].flags.value);

				if (connectorPatchFlags[i].value != 0)
					hasFramebufferPatch = true;
			}
		}
	}

	if (cpuGeneration >= CPUInfo::CpuGeneration::SandyBridge) {
		size_t patchIndex = 0;
		for (size_t i = 0; i < MaxFramebufferPatchCount; i++) {
			char name[48];
			snprintf(name, sizeof(name), "framebuffer-patch%lu-enable", i);
			// Missing status means no patches at all.
			uint32_t framebufferPatchEnable = 0;
			if (!WIOKit::getOSDataValue(igpu, name, framebufferPatchEnable))
				break;

			// False status means a temporarily disabled patch, skip for next one.
			if (!framebufferPatchEnable)
				continue;

			uint32_t framebufferId = 0;
			size_t framebufferPatchCount = 0;

			snprintf(name, sizeof(name), "framebuffer-patch%lu-framebufferid", i);
			bool passedFramebufferId = WIOKit::getOSDataValue(igpu, name, framebufferId);
			snprintf(name, sizeof(name), "framebuffer-patch%lu-find", i);
			auto framebufferPatchFind = OSDynamicCast(OSData, igpu->getProperty(name));
			snprintf(name, sizeof(name), "framebuffer-patch%lu-replace", i);
			auto framebufferPatchReplace = OSDynamicCast(OSData, igpu->getProperty(name));
			snprintf(name, sizeof(name), "framebuffer-patch%lu-count", i);
			(void)WIOKit::getOSDataValue(igpu, name, framebufferPatchCount);

			if (!framebufferPatchFind || !framebufferPatchReplace)
				continue;

			framebufferPatches[patchIndex].framebufferId = (passedFramebufferId ? framebufferId : currentFramebufferId);
			framebufferPatches[patchIndex].find = framebufferPatchFind;
			framebufferPatches[patchIndex].replace = framebufferPatchReplace;
			framebufferPatches[patchIndex].count = (framebufferPatchCount ? framebufferPatchCount : 1);

			framebufferPatchFind->retain();
			framebufferPatchReplace->retain();

			hasFramebufferPatch = true;

			patchIndex++;
		}
	}

	return hasFramebufferPatch;
}

uint8_t *IGFX::findFramebufferId(uint32_t framebufferId, uint8_t *startingAddress, size_t maxSize) {
	uint32_t *startAddress = reinterpret_cast<uint32_t *>(startingAddress);
	uint32_t *endAddress = reinterpret_cast<uint32_t *>(startingAddress + maxSize);
	while (startAddress < endAddress) {
		if (*startAddress == framebufferId)
			return reinterpret_cast<uint8_t *>(startAddress);
		startAddress++;
	}

	return nullptr;
}

#ifdef DEBUG
size_t IGFX::calculatePlatformListSize(size_t maxSize) {
	// sanity check maxSize
	if (maxSize < sizeof(uint32_t)*2)
		return maxSize;
	// ig-platform-id table ends with 0xFFFFF, but to avoid false positive
	// look for FFFFFFFF 00000000
	// and Sandy Bridge is special, ending in 00000000 000c0c0c
	uint8_t * startingAddress = reinterpret_cast<uint8_t *>(gPlatformInformationList);
	uint32_t *startAddress = reinterpret_cast<uint32_t *>(startingAddress);
	uint32_t *endAddress = reinterpret_cast<uint32_t *>(startingAddress + maxSize - sizeof(uint32_t));
	while (startAddress < endAddress) {
		if ((!gPlatformListIsSNB && 0xffffffff == startAddress[0] && 0 == startAddress[1]) ||
			(gPlatformListIsSNB && 0 == startAddress[0] && 0x0c0c0c00 == startAddress[1]))
			return reinterpret_cast<uint8_t *>(startAddress) - startingAddress + sizeof(uint32_t)*2;
		startAddress++;
	}

	return maxSize; // in case of no termination, just return maxSize
}

void IGFX::writePlatformListData(const char *subKeyName) {
	if (BaseDeviceInfo::get().cpuGeneration < CPUInfo::CpuGeneration::SandyBridge) {
		DBGLOG("igfx", "writePlatformListData unsupported below Sandy bridge");
		return;
	}
	
	auto entry = IORegistryEntry::fromPath("IOService:/IOResources/WhateverGreen");
	if (entry) {
		entry->setProperty(subKeyName, gPlatformInformationList, static_cast<unsigned>(calculatePlatformListSize(PAGE_SIZE)));
		entry->release();
	}
}
#endif

bool IGFX::applyPatch(const KernelPatcher::LookupPatch &patch, uint8_t *startingAddress, size_t maxSize) {
	bool r = false;
	size_t i = 0, patchCount = 0;
	uint8_t *startAddress = startingAddress;
	uint8_t *endAddress = startingAddress + maxSize - patch.size;

	if (startAddress < framebufferStart)
		startAddress = framebufferStart;
	if (endAddress > framebufferStart + framebufferSize)
		endAddress = framebufferStart + framebufferSize;

	while (startAddress < endAddress) {
		for (i = 0; i < patch.size; i++) {
			if (startAddress[i] != patch.find[i])
				break;
		}
		if (i == patch.size) {
			for (i = 0; i < patch.size; i++)
				startAddress[i] = patch.replace[i];

			r = true;

			if (++patchCount >= patch.count)
				break;

			startAddress += patch.size;
			continue;
		}

		startAddress++;
	}

	return r;
}

bool IGFX::setDictUInt32(OSDictionary *dict, const char *key, UInt32 value) {
    auto *num = OSNumber::withNumber(value, sizeof(UInt32));
	if (!num)
		return false;
	
	bool success = dict->setObject(key, num);
	num->release();
	return success;
}

template <>
bool IGFX::applyPlatformInformationListPatch(uint32_t framebufferId, FramebufferSNB *platformInformationList) {
	bool framebufferFound = false;

	for (size_t i = 0; i < SandyPlatformNum; i++) {
		if (sandyPlatformId[i] == framebufferId) {
			if (framebufferPatchFlags.bits.FPFMobile)
				platformInformationList[i].fMobile = framebufferPatch.fMobile;

			if (framebufferPatchFlags.bits.FPFPipeCount)
				platformInformationList[i].fPipeCount = framebufferPatch.fPipeCount;

			if (framebufferPatchFlags.bits.FPFPortCount)
				platformInformationList[i].fPortCount = framebufferPatch.fPortCount;

			if (framebufferPatchFlags.bits.FPFFBMemoryCount)
				platformInformationList[i].fFBMemoryCount = framebufferPatch.fFBMemoryCount;

			for (size_t j = 0; j < arrsize(platformInformationList[i].connectors); j++) {
				if (connectorPatchFlags[j].bits.CPFIndex)
					platformInformationList[i].connectors[j].index = framebufferPatch.connectors[j].index;

				if (connectorPatchFlags[j].bits.CPFBusId)
					platformInformationList[i].connectors[j].busId = framebufferPatch.connectors[j].busId;

				if (connectorPatchFlags[j].bits.CPFPipe)
					platformInformationList[i].connectors[j].pipe = framebufferPatch.connectors[j].pipe;

				if (connectorPatchFlags[j].bits.CPFType)
					platformInformationList[i].connectors[j].type = framebufferPatch.connectors[j].type;

				if (connectorPatchFlags[j].bits.CPFFlags)
					platformInformationList[i].connectors[j].flags = framebufferPatch.connectors[j].flags;

				if (connectorPatchFlags[j].value) {
					DBGLOG("igfx", "patching framebufferId 0x%08X connector [%d] busId: 0x%02X, pipe: %u, type: 0x%08X, flags: 0x%08X", framebufferId, platformInformationList[i].connectors[j].index, platformInformationList[i].connectors[j].busId, platformInformationList[i].connectors[j].pipe, platformInformationList[i].connectors[j].type, platformInformationList[i].connectors[j].flags.value);

					framebufferFound = true;
				}
			}

			if (framebufferPatchFlags.value) {
				DBGLOG("igfx", "patching framebufferId 0x%08X", framebufferId);
				DBGLOG("igfx", "mobile: 0x%08X", platformInformationList[i].fMobile);
				DBGLOG("igfx", "pipeCount: %u", platformInformationList[i].fPipeCount);
				DBGLOG("igfx", "portCount: %u", platformInformationList[i].fPortCount);
				DBGLOG("igfx", "fbMemoryCount: %u", platformInformationList[i].fFBMemoryCount);

				framebufferFound = true;
			}
		}
	}

	return framebufferFound;
}

// Sandy and Ivy have no flags
template <>
void IGFX::applyPlatformInformationPatchEx(FramebufferSNB *frame) {}

template <>
void IGFX::applyPlatformInformationPatchEx(FramebufferIVB *frame) {}

template <>
void IGFX::applyPlatformInformationPatchEx(FramebufferHSW *frame) {
	// fCursorMemorySize is Haswell specific
	if (framebufferPatchFlags.bits.FPFFramebufferCursorSize) {
		frame->fCursorMemorySize = fPatchCursorMemorySize;
		DBGLOG("igfx", "fCursorMemorySize: 0x%08X", frame->fCursorMemorySize);
	}

	if (framebufferPatchFlags.bits.FPFFlags)
		frame->flags.value = framebufferPatch.flags.value;

	if (framebufferPatchFlags.bits.FPFCamelliaVersion)
		frame->camelliaVersion = framebufferPatch.camelliaVersion;
}

template <typename T>
void IGFX::applyPlatformInformationPatchEx(T *frame) {
	if (framebufferPatchFlags.bits.FPFFlags)
		frame->flags.value = framebufferPatch.flags.value;


	if (framebufferPatchFlags.bits.FPFCamelliaVersion)
		frame->camelliaVersion = framebufferPatch.camelliaVersion;
}

template <typename T>
bool IGFX::applyPlatformInformationListPatch(uint32_t framebufferId, T *platformInformationList) {
	auto frame = reinterpret_cast<T *>(findFramebufferId(framebufferId, reinterpret_cast<uint8_t *>(platformInformationList), PAGE_SIZE));
	if (!frame)
		return false;

	bool r = false;

	if (framebufferPatchFlags.bits.FPFMobile)
		frame->fMobile = framebufferPatch.fMobile;

	if (framebufferPatchFlags.bits.FPFPipeCount)
		frame->fPipeCount = framebufferPatch.fPipeCount;

	if (framebufferPatchFlags.bits.FPFPortCount)
		frame->fPortCount = framebufferPatch.fPortCount;

	if (framebufferPatchFlags.bits.FPFFBMemoryCount)
		frame->fFBMemoryCount = framebufferPatch.fFBMemoryCount;

	if (framebufferPatchFlags.bits.FPFStolenMemorySize)
		frame->fStolenMemorySize = framebufferPatch.fStolenMemorySize;

	if (framebufferPatchFlags.bits.FPFFramebufferMemorySize)
		frame->fFramebufferMemorySize = framebufferPatch.fFramebufferMemorySize;

	if (framebufferPatchFlags.bits.FPFUnifiedMemorySize)
		frame->fUnifiedMemorySize = framebufferPatch.fUnifiedMemorySize;

	if (framebufferPatchFlags.value) {
		DBGLOG("igfx", "patching framebufferId 0x%08X", frame->framebufferId);
		DBGLOG("igfx", "mobile: 0x%08X", frame->fMobile);
		DBGLOG("igfx", "pipeCount: %u", frame->fPipeCount);
		DBGLOG("igfx", "portCount: %u", frame->fPortCount);
		DBGLOG("igfx", "fbMemoryCount: %u", frame->fFBMemoryCount);
		DBGLOG("igfx", "stolenMemorySize: 0x%08X", frame->fStolenMemorySize);
		DBGLOG("igfx", "framebufferMemorySize: 0x%08X", frame->fFramebufferMemorySize);
		DBGLOG("igfx", "unifiedMemorySize: 0x%08X", frame->fUnifiedMemorySize);

		r = true;
	}

	applyPlatformInformationPatchEx(frame);

	for (size_t j = 0; j < arrsize(frame->connectors); j++) {
		if (connectorPatchFlags[j].bits.CPFIndex)
			frame->connectors[j].index = framebufferPatch.connectors[j].index;

		if (connectorPatchFlags[j].bits.CPFBusId)
			frame->connectors[j].busId = framebufferPatch.connectors[j].busId;

		if (connectorPatchFlags[j].bits.CPFPipe)
			frame->connectors[j].pipe = framebufferPatch.connectors[j].pipe;

		if (connectorPatchFlags[j].bits.CPFType)
			frame->connectors[j].type = framebufferPatch.connectors[j].type;

		if (connectorPatchFlags[j].bits.CPFFlags)
			frame->connectors[j].flags = framebufferPatch.connectors[j].flags;

		if (connectorPatchFlags[j].value) {
			DBGLOG("igfx", "patching framebufferId 0x%08X connector [%d] busId: 0x%02X, pipe: %u, type: 0x%08X, flags: 0x%08X", frame->framebufferId, frame->connectors[j].index, frame->connectors[j].busId, frame->connectors[j].pipe, frame->connectors[j].type, frame->connectors[j].flags.value);

			r = true;
		}
	}

	return r;
}

template <>
bool IGFX::applyDPtoHDMIPatch(uint32_t framebufferId, FramebufferSNB *platformInformationList) {
	bool found = false;

	for (size_t i = 0; i < SandyPlatformNum; i++) {
		if (sandyPlatformId[i] == framebufferId) {
			for (size_t j = 0; j < arrsize(platformInformationList[i].connectors); j++) {
				DBGLOG("igfx", "snb connector [%lu] busId: 0x%02X, pipe: %d, type: 0x%08X, flags: 0x%08X", j, platformInformationList[i].connectors[j].busId, platformInformationList[i].connectors[j].pipe,
					   platformInformationList[i].connectors[j].type, platformInformationList[i].connectors[j].flags);

				if (platformInformationList[i].connectors[j].type == ConnectorDP) {
					platformInformationList[i].connectors[j].type = ConnectorHDMI;
					DBGLOG("igfx", "replaced snb connector %lu type from DP to HDMI", j);
					found = true;
				}
			}
		}
	}

	return found;
}

template <typename T>
bool IGFX::applyDPtoHDMIPatch(uint32_t framebufferId, T *platformInformationList) {
	auto frame = reinterpret_cast<T *>(findFramebufferId(framebufferId, reinterpret_cast<uint8_t *>(platformInformationList), PAGE_SIZE));
	if (!frame)
		return false;

	bool found = false;
	for (size_t i = 0; i < arrsize(frame->connectors); i++) {
		DBGLOG("igfx", "connector [%lu] busId: 0x%02X, pipe: %d, type: 0x%08X, flags: 0x%08X", i, platformInformationList[i].connectors[i].busId, platformInformationList[i].connectors[i].pipe,
			   platformInformationList[i].connectors[i].type, platformInformationList[i].connectors[i].flags);

		if (frame->connectors[i].type == ConnectorDP) {
			frame->connectors[i].type = ConnectorHDMI;
			DBGLOG("igfx", "replaced connector %lu type from DP to HDMI", i);
			found = true;
		}
	}

	return found;
}

void IGFX::applyFramebufferPatches() {
	auto cpuGeneration = BaseDeviceInfo::get().cpuGeneration;
	uint32_t framebufferId = framebufferPatch.framebufferId;

	// Not tested prior to 10.10.5, and definitely different on 10.9.5 at least.
	if (getKernelVersion() >= KernelVersion::Yosemite) {
		bool success = false;
		if (cpuGeneration == CPUInfo::CpuGeneration::SandyBridge)
			success = applyPlatformInformationListPatch(framebufferId, static_cast<FramebufferSNB *>(gPlatformInformationList));
		else if (cpuGeneration == CPUInfo::CpuGeneration::IvyBridge)
			success = applyPlatformInformationListPatch(framebufferId, static_cast<FramebufferIVB *>(gPlatformInformationList));
		else if (cpuGeneration == CPUInfo::CpuGeneration::Haswell)
			success = applyPlatformInformationListPatch(framebufferId, static_cast<FramebufferHSW *>(gPlatformInformationList));
		else if (cpuGeneration == CPUInfo::CpuGeneration::Broadwell)
			success = applyPlatformInformationListPatch(framebufferId, static_cast<FramebufferBDW *>(gPlatformInformationList));
		else if (cpuGeneration == CPUInfo::CpuGeneration::Skylake || cpuGeneration == CPUInfo::CpuGeneration::KabyLake ||
				 (cpuGeneration == CPUInfo::CpuGeneration::CoffeeLake && static_cast<FramebufferSKL *>(gPlatformInformationList)->framebufferId == 0x591E0000))
			//FIXME: write this in a nicer way (coffee pretending to be Kaby, detecting via first kaby frame)
			success = applyPlatformInformationListPatch(framebufferId, static_cast<FramebufferSKL *>(gPlatformInformationList));
		else if (cpuGeneration == CPUInfo::CpuGeneration::CoffeeLake)
			success = applyPlatformInformationListPatch(framebufferId, static_cast<FramebufferCFL *>(gPlatformInformationList));
		else if (cpuGeneration == CPUInfo::CpuGeneration::CometLake)
			success = applyPlatformInformationListPatch(framebufferId, static_cast<FramebufferCFL *>(gPlatformInformationList));
		else if (cpuGeneration == CPUInfo::CpuGeneration::CannonLake)
			success = applyPlatformInformationListPatch(framebufferId, static_cast<FramebufferCNL *>(gPlatformInformationList));
		else if (cpuGeneration == CPUInfo::CpuGeneration::IceLake) {
			// FIXME: Need to address possible circumstance of both ICL kexts loaded at the same time
			if (callbackIGFX->currentFramebuffer->loadIndex != KernelPatcher::KextInfo::Unloaded)
				success = applyPlatformInformationListPatch(framebufferId, static_cast<FramebufferICLLP *>(gPlatformInformationList));
			else if (callbackIGFX->currentFramebufferOpt->loadIndex != KernelPatcher::KextInfo::Unloaded)
				success = applyPlatformInformationListPatch(framebufferId, static_cast<FramebufferICLHP *>(gPlatformInformationList));
		}

		if (success)
			DBGLOG("igfx", "patching framebufferId 0x%08X successful", framebufferId);
		else
			DBGLOG("igfx", "patching framebufferId 0x%08X failed", framebufferId);
	}

	uint8_t *platformInformationAddress = findFramebufferId(framebufferId, static_cast<uint8_t *>(gPlatformInformationList), PAGE_SIZE);
	if (platformInformationAddress) {
		for (size_t i = 0; i < MaxFramebufferPatchCount; i++) {
			if (!framebufferPatches[i].find || !framebufferPatches[i].replace)
				continue;

			if (framebufferPatches[i].framebufferId != framebufferId)    {
				framebufferId = framebufferPatches[i].framebufferId;
				platformInformationAddress = findFramebufferId(framebufferId, static_cast<uint8_t *>(gPlatformInformationList), PAGE_SIZE);
			}

			if (!platformInformationAddress) {
				DBGLOG("igfx", "patch %lu framebufferId 0x%08X not found", i, framebufferId);
				continue;
			}

			if (framebufferPatches[i].find->getLength() != framebufferPatches[i].replace->getLength()) {
				DBGLOG("igfx", "patch %lu framebufferId 0x%08X length mistmatch", i, framebufferId);
				continue;
			}

			KernelPatcher::LookupPatch patch {};
			patch.kext = currentFramebuffer;
			patch.find = static_cast<const uint8_t *>(framebufferPatches[i].find->getBytesNoCopy());
			patch.replace = static_cast<const uint8_t *>(framebufferPatches[i].replace->getBytesNoCopy());
			patch.size = framebufferPatches[i].find->getLength();
			patch.count = framebufferPatches[i].count;

			if (applyPatch(patch, platformInformationAddress, PAGE_SIZE))
				DBGLOG("igfx", "patch %lu framebufferId 0x%08X successful", i, framebufferId);
			else
				DBGLOG("igfx", "patch %lu framebufferId 0x%08X failed", i, framebufferId);

			framebufferPatches[i].find->release();
			framebufferPatches[i].find = nullptr;
			framebufferPatches[i].replace->release();
			framebufferPatches[i].replace = nullptr;
		}
	}
}

void IGFX::applyHdmiAutopatch() {
	auto cpuGeneration = BaseDeviceInfo::get().cpuGeneration;
	uint32_t framebufferId = framebufferPatch.framebufferId;

	DBGLOG("igfx", "applyHdmiAutopatch framebufferId %X cpugen %X", framebufferId, cpuGeneration);

	bool success = false;
	if (cpuGeneration == CPUInfo::CpuGeneration::SandyBridge)
		success = applyDPtoHDMIPatch(framebufferId, static_cast<FramebufferSNB *>(gPlatformInformationList));
	else if (cpuGeneration == CPUInfo::CpuGeneration::IvyBridge)
		success = applyDPtoHDMIPatch(framebufferId, static_cast<FramebufferIVB *>(gPlatformInformationList));
	else if (cpuGeneration == CPUInfo::CpuGeneration::Haswell)
		success = applyDPtoHDMIPatch(framebufferId, static_cast<FramebufferHSW *>(gPlatformInformationList));
	else if (cpuGeneration == CPUInfo::CpuGeneration::Broadwell)
		success = applyDPtoHDMIPatch(framebufferId, static_cast<FramebufferBDW *>(gPlatformInformationList));
	else if (cpuGeneration == CPUInfo::CpuGeneration::Skylake || cpuGeneration == CPUInfo::CpuGeneration::KabyLake ||
			 (cpuGeneration == CPUInfo::CpuGeneration::CoffeeLake && static_cast<FramebufferSKL *>(gPlatformInformationList)->framebufferId == 0x591E0000))
		success = applyDPtoHDMIPatch(framebufferId, static_cast<FramebufferSKL *>(gPlatformInformationList));
	else if (cpuGeneration == CPUInfo::CpuGeneration::CoffeeLake)
		success = applyDPtoHDMIPatch(framebufferId, static_cast<FramebufferCFL *>(gPlatformInformationList));
	else if (cpuGeneration == CPUInfo::CpuGeneration::CometLake)
		success = applyDPtoHDMIPatch(framebufferId, static_cast<FramebufferCFL *>(gPlatformInformationList));
	else if (cpuGeneration == CPUInfo::CpuGeneration::CannonLake)
		success = applyDPtoHDMIPatch(framebufferId, static_cast<FramebufferCNL *>(gPlatformInformationList));
	else if (cpuGeneration == CPUInfo::CpuGeneration::IceLake) {
		// FIXME: Need to address possible circumstance of both ICL kexts loaded at the same time
		if (callbackIGFX->currentFramebuffer->loadIndex != KernelPatcher::KextInfo::Unloaded)
			success = applyDPtoHDMIPatch(framebufferId, static_cast<FramebufferICLLP *>(gPlatformInformationList));
		else if (callbackIGFX->currentFramebufferOpt->loadIndex != KernelPatcher::KextInfo::Unloaded)
			success = applyDPtoHDMIPatch(framebufferId, static_cast<FramebufferICLHP *>(gPlatformInformationList));
	}

	if (success)
		DBGLOG("igfx", "hdmi patching framebufferId 0x%08X successful", framebufferId);
	else
		DBGLOG("igfx", "hdmi patching framebufferId 0x%08X failed", framebufferId);
}

void IGFX::applyWestmerePatches(KernelPatcher &patcher) {
	auto kernelVersion = getKernelVersion();
	DBGLOG("igfx", "applyWestmerePatches kernel version %u", kernelVersion);

	//
	// Reference: https://github.com/Goldfish64/ArrandaleGraphicsHackintosh/blob/master/Patches.md
	//

	// Use 0x2000 for stride (fixes artifacts on resolutions > 1024x768). Located in AppleIntelHDGraphicsFB::hwSetCRTC.
	if (kernelVersion == KernelVersion::SnowLeopard) {
		static const uint8_t findStrideSnow64[] = { 0x0F, 0x85, 0x75, 0xFE, 0xFF, 0xFF, 0xE9, 0x6B, 0xFE, 0xFF, 0xFF };
		static const uint8_t replaceStrideSnow64[] = { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0xE9, 0x6B, 0xFE, 0xFF, 0xFF  };
		KernelPatcher::LookupPatch stridePatchSnow64 { currentFramebuffer, findStrideSnow64, replaceStrideSnow64, sizeof(findStrideSnow64), 1 };
		patcher.applyLookupPatch(&stridePatchSnow64);
		DBGLOG("igfx", "applyWestmerePatches applied stride patch for Snow Leopard");

	} else {
		static const uint8_t findStrideLionPlus64[] = { 0x0F, 0x45, 0xC8, 0x42, 0x89, 0x8C };
		static const uint8_t replaceStrideLionPlus64[] = { 0x90, 0x90, 0x90, 0x42, 0x89, 0x8C };
		KernelPatcher::LookupPatch stridePatchLionPlus64 { currentFramebuffer, findStrideLionPlus64, replaceStrideLionPlus64, sizeof(findStrideLionPlus64), 1 };
		patcher.applyLookupPatch(&stridePatchLionPlus64);
		DBGLOG("igfx", "applyWestmerePatches applied stride patch for Lion+");
	}

	if (framebufferPatchFlags.bitsWestmere.SingleLink && framebufferWestmerePatches.SingleLink) {
		// AAPL00,DualLink is set to <00000000> instead of patch 1.

		// Single link patch 2. Changes to divisor 14. Located in AppleIntelHDGraphicsFB::hwRegsNeedUpdate.
		if (kernelVersion == KernelVersion::SnowLeopard) {
			static const uint8_t findSingleWidth2Snow64[] = { 0xBE, 0x00, 0x00, 0x00, 0x09 };
			static const uint8_t replaceSingleWidth2Snow64[] = { 0xBE, 0x00, 0x00, 0x00, 0x08 };
			KernelPatcher::LookupPatch singleWidth2PatchSnow64 { currentFramebuffer, findSingleWidth2Snow64, replaceSingleWidth2Snow64, sizeof(findSingleWidth2Snow64), 1 };
			patcher.applyLookupPatch(&singleWidth2PatchSnow64);
			DBGLOG("igfx", "applyWestmerePatches applied single width patch 2 for Snow Leopard");

		} else if (kernelVersion == KernelVersion::Lion) {
			static const uint8_t findSingleWidth2Lion64[] = { 0xB8, 0x00, 0x00, 0x00, 0x09 };
			static const uint8_t replaceSingleWidth2Lion64[] = { 0xB8, 0x00, 0x00, 0x00, 0x08 };
			KernelPatcher::LookupPatch singleWidth2PatchLion64 { currentFramebuffer, findSingleWidth2Lion64, replaceSingleWidth2Lion64, sizeof(findSingleWidth2Lion64), 1 };
			patcher.applyLookupPatch(&singleWidth2PatchLion64);
			DBGLOG("igfx", "applyWestmerePatches applied single width patch 2 for Lion");

		} else if (kernelVersion == KernelVersion::MountainLion) {
			static const uint8_t findSingleWidth2Ml[] = { 0xB9, 0x00, 0x00, 0x00, 0x09 };
			static const uint8_t replaceSingleWidth2Ml[] = { 0xB9, 0x00, 0x00, 0x00, 0x08 };
			KernelPatcher::LookupPatch singleWidth2PatchMl { currentFramebuffer, findSingleWidth2Ml, replaceSingleWidth2Ml, sizeof(findSingleWidth2Ml), 1 };
			patcher.applyLookupPatch(&singleWidth2PatchMl);
			DBGLOG("igfx", "applyWestmerePatches applied single width patch 2 for Mountain Lion");

		} else if (kernelVersion == KernelVersion::Mavericks) {
			static const uint8_t findSingleWidth2Mav[] = { 0x41, 0xB9, 0x00, 0x60, 0x00, 0x09 };
			static const uint8_t replaceSingleWidth2Mav[] = { 0x41, 0xB9, 0x00, 0x60, 0x00, 0x08 };
			KernelPatcher::LookupPatch singleWidth2PatchMav { currentFramebuffer, findSingleWidth2Mav, replaceSingleWidth2Mav, sizeof(findSingleWidth2Mav), 1 };
			patcher.applyLookupPatch(&singleWidth2PatchMav);
			DBGLOG("igfx", "applyWestmerePatches applied single width patch 2 for Mavericks");

		} else if (kernelVersion >= KernelVersion::Yosemite && kernelVersion <= KernelVersion::Sierra) {
			static const uint8_t findSingleWidth2Yos[] = { 0xB8, 0x00, 0x60, 0x00, 0x09 };
			static const uint8_t replaceSingleWidth2Yos[] = { 0xB8, 0x00, 0x60, 0x00, 0x08 };
			KernelPatcher::LookupPatch singleWidth2PatchYos { currentFramebuffer, findSingleWidth2Yos, replaceSingleWidth2Yos, sizeof(findSingleWidth2Yos), 1 };
			patcher.applyLookupPatch(&singleWidth2PatchYos);
			DBGLOG("igfx", "applyWestmerePatches applied single width patch 2 for Yosemite to Sierra");

		} else if (kernelVersion >= KernelVersion::HighSierra) {
			static const uint8_t findSingleWidth2Hs[] = { 0xBA, 0x00, 0x60, 0x00, 0x09 };
			static const uint8_t replaceSingleWidth2Hs[] = { 0xBA, 0x00, 0x60, 0x00, 0x08 };
			KernelPatcher::LookupPatch singleWidth2PatchHs { currentFramebuffer, findSingleWidth2Hs, replaceSingleWidth2Hs, sizeof(findSingleWidth2Hs), 1 };
			patcher.applyLookupPatch(&singleWidth2PatchHs);
			DBGLOG("igfx", "applyWestmerePatches applied single width patch 2 for High Sierra+");
		}

		// Single link patch 3. Powers down CLKB (fixes pixelated image). Located in AppleIntelHDGraphicsFB::hwRegsNeedUpdate.
		static const uint8_t findSingleWidth3[] = { 0x3C, 0x03, 0x30, 0x80 };
		static const uint8_t replaceSingleWidth3[] = { 0x00, 0x03, 0x30, 0x80 };
		KernelPatcher::LookupPatch singleWidth3Patch { currentFramebuffer, findSingleWidth3, replaceSingleWidth3, sizeof(findSingleWidth3), 1 };
		patcher.applyLookupPatch(&singleWidth3Patch);
		DBGLOG("igfx", "applyWestmerePatches applied single width patch 3");
	}
}

void IGFX::wrapTrainFDI(IOService *that, int32_t value, void *params) {
	// Cap link width.
	if (callbackIGFX->framebufferWestmerePatches.LinkWidth == 0 || callbackIGFX->framebufferWestmerePatches.LinkWidth > 4) {
		SYSLOG("igfx", "link width of %u is invalid; using 1", callbackIGFX->framebufferWestmerePatches.LinkWidth);
		callbackIGFX->framebufferWestmerePatches.LinkWidth = 1;
	}
	
	auto pciDevice = OSDynamicCast(IOPCIDevice, that->getProvider());
	if (pciDevice) {
		auto baseMemoryMap = pciDevice->mapDeviceMemoryWithRegister(kIOPCIConfigBaseAddress0);
		if (baseMemoryMap) {
			auto baseAddr = (volatile void *) (baseMemoryMap->getVirtualAddress());

			// Set initial link width
			auto txaCtl = OSReadLittleInt32(baseAddr, WESTMERE_TXA_CTL) & WESTMERE_LINK_WIDTH_MASK;
			auto rxaCtl = OSReadLittleInt32(baseAddr, WESTMERE_RXA_CTL) & WESTMERE_LINK_WIDTH_MASK;
			auto linkWidth = (callbackIGFX->framebufferWestmerePatches.LinkWidth - 1) << WESTMERE_LINK_WIDTH_SHIFT;

			OSWriteLittleInt32(baseAddr, WESTMERE_TXA_CTL, txaCtl | linkWidth);
			OSWriteLittleInt32(baseAddr, WESTMERE_RXA_CTL, rxaCtl | linkWidth);
			// AppleIntelHDGraphicsFB has a delay after setting registers
			IODelay(100);

			baseMemoryMap->release();
		} else {
			SYSLOG("igfx", "failed to map BAR0");
		}
	} else {
		SYSLOG("igfx", "provider is not IOPCIDevice");
	}

	FunctionCast(wrapTrainFDI, callbackIGFX->orgTrainFDI)(that, value, params);
}

void IGFX::applyWestmereFeaturePatches(IOService *framebuffer) {
	bool success = true;

	uint32_t patchFeatureControl = 0;
	patchFeatureControl |= callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlFBC;
	patchFeatureControl |= callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlGPUInterruptHandling;
	patchFeatureControl |= callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlGamma;
	patchFeatureControl |= callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlMaximumSelfRefreshLevel;
	patchFeatureControl |= callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlPowerStates;
	patchFeatureControl |= callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlRSTimerTest;
	patchFeatureControl |= callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlRenderStandby;
	patchFeatureControl |= callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlWatermarks;

	if (callbackIGFX->framebufferPatchFlags.bitsWestmere.FBCControlCompression) {
		// Entire dictionary will always be replaced as there is only a single property.
		auto dictFBCControl = OSDictionary::withCapacity(1);
		if (dictFBCControl) {
			success &= setDictUInt32(dictFBCControl, "Compression", framebufferWestmerePatches.FBCControlCompression);

			// Replace FBCControl dictionary.
			success &= framebuffer->setProperty("FBCControl", dictFBCControl);
			dictFBCControl->release();
		} else {
			success = false;
		}
	}

	if (patchFeatureControl) {
		// Try to get existing dictionary, replace if not found.
		auto dictFeatureControlOld = OSDynamicCast(OSDictionary, framebuffer->getProperty("FeatureControl"));
		OSDictionary *dictFeatureControlNew;
		if (dictFeatureControlOld)
			dictFeatureControlNew = OSDictionary::withDictionary(dictFeatureControlOld);
		else
			dictFeatureControlNew = OSDictionary::withCapacity(8);

		// Replace any specified properties.
		if (dictFeatureControlNew) {
			if (callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlFBC)
				success &= setDictUInt32(dictFeatureControlNew, "FBC", framebufferWestmerePatches.FeatureControlFBC);
			if (callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlGPUInterruptHandling)
				success &= setDictUInt32(dictFeatureControlNew, "GPUInterruptHandling", framebufferWestmerePatches.FeatureControlGPUInterruptHandling);
			if (callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlGamma)
				success &= setDictUInt32(dictFeatureControlNew, "Gamma", framebufferWestmerePatches.FeatureControlGamma);
			if (callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlMaximumSelfRefreshLevel)
				success &= setDictUInt32(dictFeatureControlNew, "MaximumSelfRefreshLevel", framebufferWestmerePatches.FeatureControlMaximumSelfRefreshLevel);
			if (callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlPowerStates)
				success &= setDictUInt32(dictFeatureControlNew, "PowerStates", framebufferWestmerePatches.FeatureControlPowerStates);
			if (callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlRSTimerTest)
				success &= setDictUInt32(dictFeatureControlNew, "RSTimerTest", framebufferWestmerePatches.FeatureControlRSTimerTest);
			if (callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlRenderStandby)
				success &= setDictUInt32(dictFeatureControlNew, "RenderStandby", framebufferWestmerePatches.FeatureControlRenderStandby);
			if (callbackIGFX->framebufferPatchFlags.bitsWestmere.FeatureControlWatermarks)
				success &= setDictUInt32(dictFeatureControlNew, "Watermarks", framebufferWestmerePatches.FeatureControlWatermarks);

			// Replace FBCControl dictionary.
			success &= framebuffer->setProperty("FeatureControl", dictFeatureControlNew);
			dictFeatureControlNew->release();
		} else {
			success = false;
		}
	}

	if (success)
		DBGLOG("igfx", "applyWestmereFeaturePatches successful %X", callbackIGFX->framebufferPatchFlags.value);
	else
		DBGLOG("igfx", "applyWestmereFeaturePatches failed %X", callbackIGFX->framebufferPatchFlags.value);
}
