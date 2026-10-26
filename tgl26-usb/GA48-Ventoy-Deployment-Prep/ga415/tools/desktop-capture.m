// Bounded ScreenCaptureKit screenshots + CoreGraphics metadata. No injection.
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ScreenCaptureKit/ScreenCaptureKit.h>
#import <ImageIO/ImageIO.h>
#include <unistd.h>

static NSString *out;
static void json(NSString *name, id value) {
    NSError *e = nil;
    NSData *d = [NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:&e];
    if (!d || ![d writeToFile:[out stringByAppendingPathComponent:name]
                     options:NSDataWritingWithoutOverwriting error:&e]) {
        fprintf(stderr, "WRITE_FAILED %s\n", e.description.UTF8String); exit(4);
    }
}
static BOOL waitFor(dispatch_semaphore_t sem) {
    NSDate *end = [NSDate dateWithTimeIntervalSinceNow:20];
    while (dispatch_semaphore_wait(sem, DISPATCH_TIME_NOW)) {
        if (end.timeIntervalSinceNow < 0) return NO;
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.01]];
    }
    return YES;
}
static NSDictionary *snapshot(SCContentFilter *filter, NSString *name, size_t width, size_t height) {
    SCStreamConfiguration *cfg = [SCStreamConfiguration new];
    cfg.width = width; cfg.height = height; cfg.showsCursor = NO;
    cfg.captureResolution = SCCaptureResolutionBest;
    __block NSDictionary *row = nil;
    dispatch_semaphore_t sem = dispatch_semaphore_create(0);
    [SCScreenshotManager captureImageWithFilter:filter configuration:cfg
        completionHandler:^(CGImageRef image, NSError *error) {
        if (!image || error) {
            row = @{ @"file":name, @"RESULT":@"CAPTURE_PATH_UNVERIFIED", @"error":error.description ?: @"NIL_IMAGE" };
        } else {
            NSString *path = [out stringByAppendingPathComponent:name];
            CGImageDestinationRef dst = CGImageDestinationCreateWithURL((__bridge CFURLRef)[NSURL fileURLWithPath:path],
                                                                       CFSTR("public.png"), 1, NULL);
            BOOL ok = NO;
            if (dst) { CGImageDestinationAddImage(dst, image, NULL); ok = CGImageDestinationFinalize(dst); CFRelease(dst); }
            CGColorSpaceRef cs = CGImageGetColorSpace(image);
            CFStringRef csName = cs ? CGColorSpaceCopyName(cs) : NULL;
            row = @{ @"file":name, @"RESULT":ok ? @"CAPTURE_COMPLETE_UNVERIFIED" : @"CAPTURE_INVALID",
                @"width":@(CGImageGetWidth(image)), @"height":@(CGImageGetHeight(image)),
                @"bits_per_component":@(CGImageGetBitsPerComponent(image)),
                @"bits_per_pixel":@(CGImageGetBitsPerPixel(image)), @"image_bpr":@(CGImageGetBytesPerRow(image)),
                @"alpha_info":@(CGImageGetAlphaInfo(image)), @"color_space":csName ? (__bridge NSString *)csName : @"NOT_OBSERVED",
                @"capture_API":@"SCScreenshotManager; proxy through system capture path" };
            if (csName) CFRelease(csName);
        }
        dispatch_semaphore_signal(sem);
    }];
    if (!waitFor(sem)) return @{ @"file":name, @"RESULT":@"CAPTURE_PATH_UNVERIFIED", @"error":@"CAPTURE_TIMEOUT" };
    return row;
}
int main(int argc, char **argv) { @autoreleasepool {
    BOOL request = NO, metadataOnly = NO; uint32_t windowID = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--output") && i + 1 < argc) out = @(argv[++i]);
        else if (!strcmp(argv[i], "--window") && i + 1 < argc) windowID = (uint32_t)strtoul(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--request-permission")) request = YES;
        else if (!strcmp(argv[i], "--metadata-only")) metadataOnly = YES;
        else { fprintf(stderr, "usage: desktop-capture --output NEW_DIR [--window ID] [--metadata-only] [--request-permission]\n"); return 2; }
    }
    NSError *e = nil;
    if (!out || [[NSFileManager defaultManager] fileExistsAtPath:out] ||
        ![[NSFileManager defaultManager] createDirectoryAtPath:out withIntermediateDirectories:NO attributes:nil error:&e]) return 2;
    alarm(100); // Process deadline; not a GPU cancellation mechanism.
    BOOL access = CGPreflightScreenCaptureAccess();
    if (!access && request && !metadataOnly) access = CGRequestScreenCaptureAccess();
    NSArray *windows = CFBridgingRelease(CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID));
    json(@"windows.json", windows ?: @[]);
    CGDirectDisplayID ids[16]; uint32_t count = 0;
    CGError displayError = CGGetActiveDisplayList(16, ids, &count);
    NSMutableArray *displays = [NSMutableArray array];
    for (uint32_t i = 0; i < count; i++) {
        CGDisplayModeRef m = CGDisplayCopyDisplayMode(ids[i]);
        CGRect b = CGDisplayBounds(ids[i]);
        [displays addObject:@{@"id":@(ids[i]), @"main":@(ids[i] == CGMainDisplayID()),
            @"bounds":@[@(b.origin.x),@(b.origin.y),@(b.size.width),@(b.size.height)],
            @"framebuffer_width":@(CGDisplayPixelsWide(ids[i])), @"framebuffer_height":@(CGDisplayPixelsHigh(ids[i])),
            @"mode_width":@(m ? CGDisplayModeGetWidth(m) : 0), @"mode_height":@(m ? CGDisplayModeGetHeight(m) : 0),
            @"mode_pixel_width":@(m ? CGDisplayModeGetPixelWidth(m) : 0), @"mode_pixel_height":@(m ? CGDisplayModeGetPixelHeight(m) : 0),
            @"refresh_hz":m && CGDisplayModeGetRefreshRate(m) > 0 ? @(CGDisplayModeGetRefreshRate(m)) : @"NOT_OBSERVED",
            @"scale_x":@(b.size.width ? CGDisplayPixelsWide(ids[i]) / b.size.width : 0),
            @"scanout_color_format":@"NOT_OBSERVED"}];
        if (m) CGDisplayModeRelease(m);
    }
    NSMutableDictionary *report = [@{@"schema":@"ga415-desktop-capture-v1", @"utc":[NSDate date].description,
        @"pid":@(getpid()), @"screen_recording_preflight":@(access), @"permission_request_explicit":@(request),
        @"displays":displays, @"display_API_error":@(displayError),
        @"coordinate_convention":@"CoreGraphics logical top-left window bounds; PNG ROI coordinates are image pixels",
        @"RESULT":@"CAPTURE_PATH_UNVERIFIED",
        @"limits":@"Different full-display/window filters are different capture paths. Blank pixels alone do not prove GPU corruption."} mutableCopy];
    if (metadataOnly || !access) {
        report[@"reason"] = metadataOnly ? @"METADATA_ONLY" : @"SCREEN_RECORDING_PERMISSION_UNAVAILABLE";
        report[@"GUI_next_step"] = @"Run from logged-in Terminal: desktop-capture --request-permission --output NEW_DIR; approve Screen Recording if prompted, then relaunch after authorization. No automatic TCC changes.";
        json(@"capture.json", report); return metadataOnly ? 0 : 3;
    }
    __block SCShareableContent *content = nil; __block NSError *shareError = nil;
    dispatch_semaphore_t sem = dispatch_semaphore_create(0);
    [SCShareableContent getShareableContentExcludingDesktopWindows:NO onScreenWindowsOnly:YES
        completionHandler:^(SCShareableContent *c, NSError *err) { content = c; shareError = err; dispatch_semaphore_signal(sem); }];
    if (!waitFor(sem) || !content) {
        report[@"reason"] = shareError.description ?: @"SHAREABLE_CONTENT_TIMEOUT";
        json(@"capture.json", report); return 3;
    }
    NSMutableArray *captures = [NSMutableArray array];
    for (SCDisplay *d in content.displays) if (d.displayID == CGMainDisplayID()) {
        SCContentFilter *f = [[SCContentFilter alloc] initWithDisplay:d excludingWindows:@[]];
        [captures addObject:snapshot(f, @"desktop.png", CGDisplayPixelsWide(d.displayID), CGDisplayPixelsHigh(d.displayID))];
    }
    unsigned taken = 0;
    for (SCWindow *w in content.windows) {
        NSString *owner = w.owningApplication.applicationName ?: @"";
        BOOL selected = windowID ? w.windowID == windowID :
            ([owner containsString:@"System Settings"] || [owner containsString:@"系统设置"] || [owner isEqualToString:@"Dock"]);
        if (selected && w.frame.size.width > 10 && w.frame.size.height > 10 && taken < 3) {
            SCContentFilter *f = [[SCContentFilter alloc] initWithDesktopIndependentWindow:w];
            NSDictionary *cap = snapshot(f, [NSString stringWithFormat:@"window-%u.png", w.windowID],
                                         (size_t)(w.frame.size.width * f.pointPixelScale), (size_t)(w.frame.size.height * f.pointPixelScale));
            NSMutableDictionary *row = [cap mutableCopy]; row[@"window_id"] = @(w.windowID); row[@"owner"] = owner;
            row[@"logical_bounds"] = @[@(w.frame.origin.x),@(w.frame.origin.y),@(w.frame.size.width),@(w.frame.size.height)];
            [captures addObject:row]; taken++;
        }
    }
    report[@"captures"] = captures;
    BOOL ok = captures.count > 0;
    for (NSDictionary *r in captures) if (![r[@"RESULT"] isEqual:@"CAPTURE_COMPLETE_UNVERIFIED"]) ok = NO;
    report[@"RESULT"] = ok ? @"CAPTURE_COMPLETE_UNVERIFIED" : @"CAPTURE_PATH_UNVERIFIED";
    json(@"capture.json", report); alarm(0); return ok ? 0 : 3;
} }
