import AppKit
import Foundation
import Vision

struct CropSpec: Codable {
    let path: String
    let status: String
    let page: Int
    let row: Int
    let field: String
    let centerX: Double
    let centerY: Double
    let width: Double
    let height: Double
}

struct CropResult: Codable {
    let status: String
    let page: Int
    let row: Int
    let field: String
    let recognized: String?
}

guard CommandLine.arguments.count == 3 else {
    fputs("Usage: ocr_ghin_cell_crops.swift specs.json output.json\n", stderr)
    exit(2)
}

let specsURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
let specs = try JSONDecoder().decode([CropSpec].self, from: Data(contentsOf: specsURL))
var cachedImages: [String: CGImage] = [:]
var results: [CropResult] = []

for spec in specs {
    let cgImage: CGImage
    if let cached = cachedImages[spec.path] {
        cgImage = cached
    } else {
        guard let image = NSImage(contentsOfFile: spec.path),
              let data = image.tiffRepresentation,
              let bitmap = NSBitmapImageRep(data: data),
              let loaded = bitmap.cgImage else {
            throw NSError(domain: "GHINOCR", code: 1, userInfo: [NSLocalizedDescriptionKey: "Unable to load \(spec.path)"])
        }
        cachedImages[spec.path] = loaded
        cgImage = loaded
    }

    let left = max(0, spec.centerX - spec.width / 2)
    let bottom = max(0, spec.centerY - spec.height / 2)
    let rect = CGRect(
        x: left * Double(cgImage.width),
        y: (1 - bottom - spec.height) * Double(cgImage.height),
        width: spec.width * Double(cgImage.width),
        height: spec.height * Double(cgImage.height)
    ).integral
    guard let crop = cgImage.cropping(to: rect) else {
        results.append(CropResult(status: spec.status, page: spec.page, row: spec.row, field: spec.field, recognized: nil))
        continue
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.minimumTextHeight = 0.01
    try VNImageRequestHandler(cgImage: crop).perform([request])
    let text = (request.results ?? [])
        .compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: " ")
    let numeric = text.range(of: #"\d+"#, options: .regularExpression).map { String(text[$0]) }
    results.append(CropResult(status: spec.status, page: spec.page, row: spec.row, field: spec.field, recognized: numeric))
}

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
try encoder.encode(results).write(to: outputURL)
print("Wrote \(results.count) crop results")
