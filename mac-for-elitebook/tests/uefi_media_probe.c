/* Isolated QEMU probe of image-backed EFI filesystem/block handles.
 * Reads one marker; never writes a filesystem or firmware variable.
 * Debug I/O ports are QEMU-only test devices.
 */
#include <efi.h>

static void emit(const char *s) {
    while (*s) __asm__ volatile ("outb %0, %1" : : "a"((UINT8)*s++), "Nd"((UINT16)0xE9));
}

static void number(UINTN n) {
    char b[24]; UINTN i = 0;
    do { b[i++] = (char)('0' + n % 10); n /= 10; } while (n);
    while (i) { char s[] = {b[--i], 0}; emit(s); }
}

static int marker(EFI_BOOT_SERVICES *bs, EFI_HANDLE device) {
    EFI_GUID guid = EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_GUID;
    EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *fs = NULL;
    EFI_FILE_HANDLE root = NULL, file = NULL;
    EFI_STATUS status = bs->HandleProtocol(device, &guid, (void **)&fs);
    if (EFI_ERROR(status) || !fs) return 0;
    status = fs->OpenVolume(fs, &root);
    if (EFI_ERROR(status) || !root) return 0;
    status = root->Open(root, &file, L"\\OCMEDIAPROBE.TXT", EFI_FILE_MODE_READ, 0);
    int match = 0;
    if (!EFI_ERROR(status) && file) {
        char buffer[32]; UINTN length = sizeof(buffer);
        status = file->Read(file, &length, buffer);
        const char expected[] = "OC_MEDIA_PROBE_2026\n";
        match = !EFI_ERROR(status) && length == sizeof(expected) - 1;
        for (UINTN i = 0; match && i < length; ++i) if (buffer[i] != expected[i]) match = 0;
        file->Close(file);
    }
    root->Close(root);
    return match;
}

EFI_STATUS EFIAPI efi_main(EFI_HANDLE image, EFI_SYSTEM_TABLE *system) {
    EFI_BOOT_SERVICES *bs = system->BootServices;
    EFI_GUID loaded_guid = LOADED_IMAGE_PROTOCOL;
    EFI_GUID fs_guid = EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_GUID;
    EFI_GUID block_guid = BLOCK_IO_PROTOCOL;
    EFI_GUID path_guid = DEVICE_PATH_PROTOCOL;
    EFI_LOADED_IMAGE *loaded = NULL;
    emit("UEFI_MEDIA_PROBE_BEGIN\n");
    EFI_STATUS status = bs->HandleProtocol(image, &loaded_guid, (void **)&loaded);
    int loaded_device = !EFI_ERROR(status) && loaded && loaded->DeviceHandle;
    emit("LOADED_DEVICE_HANDLE="); number(loaded_device); emit("\n");
    emit("LOADED_DEVICE_MARKER="); number(loaded_device && marker(bs, loaded->DeviceHandle)); emit("\n");
    EFI_HANDLE *handles = NULL; UINTN count = 0, found = 0, block_found = 0;
    status = bs->LocateHandleBuffer(ByProtocol, &fs_guid, NULL, &count, &handles);
    if (!EFI_ERROR(status)) {
        emit("SIMPLEFS_HANDLES="); number(count); emit("\n");
        for (UINTN i = 0; i < count; ++i) {
            if (!marker(bs, handles[i])) continue;
            ++found;
            EFI_BLOCK_IO *block = NULL;
            status = bs->HandleProtocol(handles[i], &block_guid, (void **)&block);
            int block_ok = !EFI_ERROR(status) && block && block->Media && block->Media->MediaPresent;
            block_found += block_ok;
            emit("MARKER_HANDLE_BLOCKIO="); number(block_ok); emit("\n");
            if (block_ok) {
                emit("MARKER_BLOCK_SIZE="); number(block->Media->BlockSize); emit("\n");
                emit("MARKER_LAST_BLOCK="); number(block->Media->LastBlock); emit("\n");
            }
            EFI_DEVICE_PATH *path = NULL;
            status = bs->HandleProtocol(handles[i], &path_guid, (void **)&path);
            emit("MARKER_DEVICE_PATH=");
            for (UINTN j = 0; !EFI_ERROR(status) && path && j < 64; ++j) {
                number(path->Type); emit(":"); number(path->SubType); emit(" ");
                UINTN length = path->Length[0] | ((UINTN)path->Length[1] << 8);
                if (length < sizeof(*path) || path->Type == 0x7F) break;
                path = (EFI_DEVICE_PATH *)((UINT8 *)path + length);
            }
            emit("\n");
        }
        bs->FreePool(handles);
    }
    emit("MARKER_FILESYSTEMS="); number(found); emit("\n");
    emit("MARKER_BLOCK_HANDLES="); number(block_found); emit("\n");
    emit("UEFI_MEDIA_PROBE_END\n");
    __asm__ volatile ("outl %0, %1" : : "a"(found && block_found ? 0x10U : 0x11U), "Nd"((UINT16)0xF4));
    for (;;) __asm__ volatile ("hlt");
}
