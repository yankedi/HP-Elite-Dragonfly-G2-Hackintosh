// CPU-only resource layout check; no Metal device, texture, queue or submission.
#import <Foundation/Foundation.h>
#import <CoreVideo/CoreVideo.h>
#import <IOSurface/IOSurface.h>

int main(void) { @autoreleasepool {
    const OSType formats[] = {kCVPixelFormatType_32BGRA,
        kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange,
        kCVPixelFormatType_420YpCbCr8BiPlanarFullRange};
    NSMutableArray *rows = [NSMutableArray array];
    BOOL all = YES;
    for (unsigned i = 0; i < 3; i++) {
        CVPixelBufferRef buffer = NULL;
        NSDictionary *attributes = @{(__bridge NSString *)kCVPixelBufferIOSurfacePropertiesKey:@{}};
        CVReturn status = CVPixelBufferCreate(kCFAllocatorDefault, 64, 32, formats[i],
            (__bridge CFDictionaryRef)attributes, &buffer);
        IOSurfaceRef surface = buffer ? CVPixelBufferGetIOSurface(buffer) : NULL;
        size_t count = surface ? IOSurfaceGetPlaneCount(surface) : 0;
        size_t expectedCount = i == 0 ? 0 : 2;
        BOOL ok = status == kCVReturnSuccess && surface && count == expectedCount;
        NSMutableArray *planes = [NSMutableArray array];
        if (surface) {
            for (size_t p = 0; p < (count ? count : 1); p++) {
                size_t w = count ? IOSurfaceGetWidthOfPlane(surface, p) : IOSurfaceGetWidth(surface);
                size_t h = count ? IOSurfaceGetHeightOfPlane(surface, p) : IOSurfaceGetHeight(surface);
                size_t bpr = count ? IOSurfaceGetBytesPerRowOfPlane(surface, p) : IOSurfaceGetBytesPerRow(surface);
                size_t bpe = count ? IOSurfaceGetBytesPerElementOfPlane(surface, p) : IOSurfaceGetBytesPerElement(surface);
                ok = ok && w > 0 && h > 0 && bpe > 0 && bpr >= w * bpe;
                [planes addObject:@{@"index":@(p), @"width":@(w), @"height":@(h), @"bpr":@(bpr), @"bytes_per_element":@(bpe)}];
            }
        }
        all = all && ok;
        [rows addObject:@{@"format":@(formats[i]), @"CVPixelBufferCreate_status":@(status),
            @"IOSurface_exists":@(surface != NULL), @"actual_plane_count":@(count),
            @"expected_plane_count":@(expectedCount), @"planes":planes,
            @"RESULT":ok ? @"CPU_IOSURFACE_LAYOUT_PASS" : @"CPU_IOSURFACE_LAYOUT_FAIL"}];
        if (buffer) CVPixelBufferRelease(buffer);
    }
    NSDictionary *report = @{@"status":all ? @"CPU_IOSURFACE_LAYOUT_PASS" : @"CPU_IOSURFACE_LAYOUT_FAIL",
        @"cases":rows, @"GPU_submitted":@NO, @"Metal_device_created":@NO,
        @"limits":@"Checks legal current-system public CPU layouts only. Not a PLANES2 kernel runtime or GPU pixel validation."};
    NSData *data = [NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:NULL];
    puts([[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding].UTF8String);
    return all ? 0 : 1;
} }
