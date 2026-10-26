/* A real UEFI application, run only inside the isolated QEMU test guest.
 * Checks firmware protocols installed by the actual OpenCore/OpenHfsPlus drivers.
 * All I/O instructions address QEMU's debugcon/debug-exit test devices.
 */
#include <efi.h>

static void emit(const char *text) {
    while (*text) {
        __asm__ volatile ("outb %0, %1" : : "a"((UINT8)*text++), "Nd"((UINT16)0xE9));
    }
}

static void number(UINTN value) {
    char buffer[24];
    UINTN count = 0;
    do { buffer[count++] = (char)('0' + value % 10); value /= 10; } while (value);
    while (count) {
        char one[] = { buffer[--count], 0 };
        emit(one);
    }
}

static int equal_guid(const EFI_GUID *a, const EFI_GUID *b) {
    const UINT8 *left = (const UINT8 *)a, *right = (const UINT8 *)b;
    for (UINTN i = 0; i < sizeof(*a); ++i) if (left[i] != right[i]) return 0;
    return 1;
}

static int equal_text(const CHAR16 *a, const CHAR16 *b) {
    if (!a || !b) return 0;
    for (UINTN i = 0; i < 128; ++i) {
        if (a[i] != b[i]) return 0;
        if (!a[i]) return 1;
    }
    return 0;
}

static int path_contains(EFI_DEVICE_PATH *path, const CHAR16 *needle) {
    for (UINTN node_count = 0; path && node_count < 128; ++node_count) {
        UINTN length = path->Length[0] | ((UINTN)path->Length[1] << 8);
        if (length < sizeof(*path) || path->Type == 0x7F) break;
        if (path->Type == 4 && path->SubType == 4) {
            const CHAR16 *name = (const CHAR16 *)(path + 1);
            UINTN characters = (length - sizeof(*path)) / sizeof(CHAR16);
            for (UINTN i = 0; i < characters; ++i) {
                UINTN j = 0;
                while (needle[j] && i + j < characters && name[i+j] == needle[j]) ++j;
                if (!needle[j]) return 1;
            }
        }
        path = (EFI_DEVICE_PATH *)((UINT8 *)path + length);
    }
    return 0;
}

EFI_STATUS EFIAPI efi_main(EFI_HANDLE image, EFI_SYSTEM_TABLE *system) {
    (void)image;
    emit("UEFI_COMPONENT_PROBE_BEGIN\n");
    EFI_GUID runtime_guid = {0x570332E4,0xFC50,0x4B21,{0xAB,0xE8,0xAE,0x72,0xF0,0x5B,0x4F,0xF7}};
    EFI_GUID image_guid = LOADED_IMAGE_PROTOCOL;
    EFI_GUID binding_guid = EFI_DRIVER_BINDING_PROTOCOL_GUID;
    EFI_GUID name_guid = EFI_COMPONENT_NAME_PROTOCOL_GUID;
    EFI_GUID gop_guid = EFI_GRAPHICS_OUTPUT_PROTOCOL_GUID;
    EFI_GUID acpi_guid = ACPI_20_TABLE_GUID;
    UINTN *runtime = NULL;
    EFI_STATUS status = system->BootServices->LocateProtocol(&runtime_guid, NULL, (void **)&runtime);
    int runtime_ok = !EFI_ERROR(status) && runtime && runtime[0] == 12;
    emit("OPENRUNTIME_REVISION_12="); number(runtime_ok); emit("\n");

    UINTN count = 0;
    EFI_HANDLE *handles = NULL;
    int hfs_started = 0, hfs_path = 0;
    status = system->BootServices->LocateHandleBuffer(ByProtocol, &binding_guid, NULL, &count, &handles);
    if (!EFI_ERROR(status)) {
        for (UINTN i = 0; i < count; ++i) {
            EFI_DRIVER_BINDING_PROTOCOL *binding = NULL;
            EFI_LOADED_IMAGE *loaded = NULL;
            status = system->BootServices->HandleProtocol(handles[i], &binding_guid, (void **)&binding);
            if (EFI_ERROR(status) || !binding) continue;
            status = system->BootServices->HandleProtocol(binding->ImageHandle, &image_guid, (void **)&loaded);
            if (EFI_ERROR(status) || !loaded) continue;
            EFI_COMPONENT_NAME_PROTOCOL *component = NULL;
            status = system->BootServices->HandleProtocol(handles[i], &name_guid, (void **)&component);
            if (EFI_ERROR(status) || !component) continue;
            CHAR16 *name = NULL;
            status = component->GetDriverName(component, (CHAR8 *)"eng", &name);
            // Pinned fsw_efi.c/GetDriverName and OpenHfsPlus.inf/-DFSTYPE=hfsplus.
            // OpenCore can load from a buffer without retaining a filename device path.
            if (!EFI_ERROR(status) && equal_text(name, L"Fsw hfsplus File System Driver")) {
                hfs_started = 1;
                hfs_path = path_contains(loaded->FilePath, L"OpenHfsPlus.efi");
            }
        }
        system->BootServices->FreePool(handles);
    }
    emit("HFSPLUS_DRIVER_BINDING="); number(hfs_started); emit("\n");
    emit("HFSPLUS_IMAGE_PATH_MATCH="); number(hfs_path); emit("\n");

    EFI_GRAPHICS_OUTPUT_PROTOCOL *gop = NULL;
    status = system->BootServices->LocateProtocol(&gop_guid, NULL, (void **)&gop);
    int gop_ok = !EFI_ERROR(status) && gop && gop->Mode && gop->Mode->Info;
    emit("VIRTUAL_GOP="); number(gop_ok); emit("\n");
    if (gop_ok) {
        emit("VIRTUAL_GOP_WIDTH="); number(gop->Mode->Info->HorizontalResolution); emit("\n");
        emit("VIRTUAL_GOP_HEIGHT="); number(gop->Mode->Info->VerticalResolution); emit("\n");
    }
    int acpi_ok = 0;
    for (UINTN i = 0; i < system->NumberOfTableEntries; ++i) {
        if (equal_guid(&system->ConfigurationTable[i].VendorGuid, &acpi_guid)) acpi_ok = 1;
    }
    emit("VIRTUAL_ACPI_2_TABLE="); number(acpi_ok); emit("\n");
    emit("MACOS_KERNEL_EXECUTED=0\nKEXT_EXECUTED=0\n");
    int success = runtime_ok && hfs_started && gop_ok && acpi_ok;
    emit(success ? "UEFI_COMPONENT_PROBE_PASS\n" : "UEFI_COMPONENT_PROBE_MISSING_COMPONENT\n");
    __asm__ volatile ("outl %0, %1" : : "a"(success ? 0x10U : 0x11U), "Nd"((UINT16)0xF4));
    for (;;) __asm__ volatile ("hlt");
}
