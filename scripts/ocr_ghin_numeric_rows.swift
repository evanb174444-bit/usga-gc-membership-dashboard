import AppKit
import Foundation
import Vision

struct RowSpec: Codable {
    let path: String
    let status: String
    let page: Int
    let row: Int
    let centerY: Double
}

struct RowResult: Codable {
    let status: String
    let page: Int
    let row: Int
    let recognized: [String]
    let numbers: [PositionedNumber]
}

struct PositionedNumber: Codable {
    let value: Int
    let x: Double
}

guard CommandLine.arguments.count == 3 || CommandLine.arguments.count == 4 else {
    fputs("Usage: ocr_ghin_numeric_rows.swift specs.json output.json\n", stderr)
    exit(2)
}

let specs = try JSONDecoder().decode(
    [RowSpec].self,
    from: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
)
var cachedImages: [String: CGImage] = [:]
var results: [RowResult] = []

for spec in specs {
    let image: CGImage
    if let cached = cachedImages[spec.path] {
        image = cached
    } else {
        guard let source = NSImage(contentsOfFile: spec.path),
              let data = source.tiffRepresentation,
              let bitmap = NSBitmapImageRep(data: data),
              let loaded = bitmap.cgImage else {
            throw NSError(domain: "GHINOCR", code: 1)
        }
        cachedImages[spec.path] = loaded
        image = loaded
    }

    // Include Status plus all three numeric columns. Vision is more reliable
    // when it sees the row context than when each one-digit cell is isolated.
    let left = 0.68
    let width = 0.31
    let height = 0.022
    let bottom = max(0, spec.centerY - height / 2)
    let rect = CGRect(
        x: left * Double(image.width),
        y: (1 - bottom - height) * Double(image.height),
        width: width * Double(image.width),
        height: height * Double(image.height)
    ).integral
    guard let crop = image.cropping(to: rect) else {
        results.append(RowResult(status: spec.status, page: spec.page, row: spec.row, recognized: [], numbers: []))
        continue
    }
    let scale = 4
    guard let context = CGContext(
        data: nil,
        width: crop.width * scale,
        height: crop.height * scale,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
    ) else { throw NSError(domain: "GHINOCR", code: 2) }
    context.interpolationQuality = .high
    context.setFillColor(NSColor.white.cgColor)
    context.fill(CGRect(x: 0, y: 0, width: crop.width * scale, height: crop.height * scale))
    context.draw(crop, in: CGRect(x: 0, y: 0, width: crop.width * scale, height: crop.height * scale))
    guard let enlarged = context.makeImage() else { throw NSError(domain: "GHINOCR", code: 3) }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = CommandLine.arguments.contains("--fast") ? .fast : .accurate
    request.usesLanguageCorrection = false
    request.minimumTextHeight = 0.01
    try VNImageRequestHandler(cgImage: enlarged).perform([request])
    let observations = request.results ?? []
    let strings = observations.compactMap { $0.topCandidates(1).first?.string }
    let numbers = observations.compactMap { observation -> PositionedNumber? in
        guard let text = observation.topCandidates(1).first?.string,
              let value = Int(text) else { return nil }
        return PositionedNumber(value: value, x: observation.boundingBox.midX)
    }
    results.append(RowResult(status: spec.status, page: spec.page, row: spec.row, recognized: strings, numbers: numbers))
}

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
try encoder.encode(results).write(to: URL(fileURLWithPath: CommandLine.arguments[2]))
print("Wrote \(results.count) numeric row results")
