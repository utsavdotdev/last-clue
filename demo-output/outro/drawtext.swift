import AppKit
import CoreText
import Foundation

struct Plate {
    let name: String
    let text: String
    let fontPath: String
    let size: CGFloat
    let hex: String
    let width: Int
    let height: Int
}

func registerFont(path: String) {
    let url = URL(fileURLWithPath: path) as CFURL
    CTFontManagerRegisterFontsForURL(url, .process, nil)
}

func color(hex: String) -> NSColor {
    var value = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
    if value.count == 6 { value = "FF" + value }
    var int: UInt64 = 0
    Scanner(string: value).scanHexInt64(&int)
    let a = CGFloat((int & 0xFF000000) >> 24) / 255
    let r = CGFloat((int & 0x00FF0000) >> 16) / 255
    let g = CGFloat((int & 0x0000FF00) >> 8) / 255
    let b = CGFloat(int & 0x000000FF) / 255
    return NSColor(srgbRed: r, green: g, blue: b, alpha: a)
}

func render(_ plate: Plate, destDir: URL) {
    registerFont(path: plate.fontPath)
    let desc = CTFontManagerCreateFontDescriptorsFromURL(URL(fileURLWithPath: plate.fontPath) as CFURL) as? [CTFontDescriptor]
    let postscript = desc?.first.flatMap { CTFontDescriptorCopyAttribute($0, kCTFontNameAttribute) as? String }
    let font = (postscript.flatMap { NSFont(name: $0, size: plate.size) }) ?? NSFont.boldSystemFont(ofSize: plate.size)

    let style = NSMutableParagraphStyle()
    style.alignment = .center
    let attrs: [NSAttributedString.Key: Any] = [
        .font: font,
        .foregroundColor: color(hex: plate.hex),
        .paragraphStyle: style,
        .kern: plate.size * (plate.name == "wordmark" ? 0.02 : plate.name == "tech" || plate.name == "oss" ? 0.10 : 0.02)
    ]
    let str = NSAttributedString(string: plate.text, attributes: attrs)
    let box = NSSize(width: plate.width, height: plate.height)
    let bound = str.boundingRect(with: box, options: [.usesLineFragmentOrigin])
    let y = (CGFloat(plate.height) - bound.height) / 2

    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: plate.width,
        pixelsHigh: plate.height,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ) else {
        fputs("failed to write \(plate.name)\n", stderr)
        exit(1)
    }
    rep.size = box
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    NSColor.clear.setFill()
    NSBezierPath(rect: NSRect(origin: .zero, size: box)).fill()
    str.draw(with: NSRect(x: 0, y: y, width: box.width, height: bound.height), options: [.usesLineFragmentOrigin])
    NSGraphicsContext.restoreGraphicsState()

    guard let png = rep.representation(using: .png, properties: [:]) else {
        fputs("failed to write \(plate.name)\n", stderr)
        exit(1)
    }
    try! png.write(to: destDir.appendingPathComponent("\(plate.name).png"))
}

let root = URL(fileURLWithPath: CommandLine.arguments[1])
let fonts = root.appendingPathComponent("assets/fonts")
let dest = root.appendingPathComponent("assets/plates")
try FileManager.default.createDirectory(at: dest, withIntermediateDirectories: true)

let extra = fonts.appendingPathComponent("DMSans-ExtraBold.ttf").path
let italic = fonts.appendingPathComponent("DMSans-Italic.ttf").path

let plates = [
    Plate(name: "remain", text: "THE GAME ENDS. THE GHOST REMAINS.", fontPath: extra, size: 44, hex: "#00142F", width: 1800, height: 120),
    Plate(name: "wordmark", text: "THE LAST CLUE", fontPath: extra, size: 92, hex: "#00142F", width: 1800, height: 160),
    Plate(name: "tagline", text: "One Word. One Imposter. Zero Trust.", fontPath: italic, size: 30, hex: "#556070", width: 1600, height: 80),
    Plate(name: "tech", text: "ARDUINO UNO Q × LOCAL AI", fontPath: extra, size: 20, hex: "#556070", width: 1400, height: 56),
    Plate(name: "oss", text: "OPEN SOURCE PROJECT", fontPath: extra, size: 18, hex: "#556070", width: 1200, height: 52),
]

for plate in plates {
    render(plate, destDir: dest)
    fputs("wrote \(plate.name)\n", stderr)
}
