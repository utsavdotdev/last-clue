import AppKit
import Foundation

let args = CommandLine.arguments
guard args.count >= 5 else {
    fputs("usage: raster_svg.swift <svg> <png> <width> <height>\n", stderr)
    exit(1)
}

let src = URL(fileURLWithPath: args[1])
let dest = URL(fileURLWithPath: args[2])
let width = Int(args[3])!
let height = Int(args[4])!

guard let image = NSImage(contentsOf: src) else {
    fputs("could not load \(src.path)\n", stderr)
    exit(1)
}

guard let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: width,
    pixelsHigh: height,
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
) else {
    fputs("could not create bitmap\n", stderr)
    exit(1)
}
rep.size = NSSize(width: width, height: height)

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
NSGraphicsContext.current?.imageInterpolation = .high
NSColor.clear.setFill()
NSBezierPath(rect: NSRect(x: 0, y: 0, width: width, height: height)).fill()
image.draw(
    in: NSRect(x: 0, y: 0, width: width, height: height),
    from: .zero,
    operation: .sourceOver,
    fraction: 1,
    respectFlipped: true,
    hints: [.interpolation: NSImageInterpolation.high]
)
NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else {
    fputs("could not encode png\n", stderr)
    exit(1)
}
try png.write(to: dest)
