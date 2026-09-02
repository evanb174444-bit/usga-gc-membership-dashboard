import AppKit
import Foundation
import Vision

struct TextObservation: Codable {
    let text: String
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

let rawArguments = Array(CommandLine.arguments.dropFirst())
guard !rawArguments.isEmpty else {
    fputs("Usage: extract_screenshot_text.swift [--output file.jsonl] image.png [...]\n", stderr)
    exit(2)
}

var arguments = rawArguments
var outputHandle = FileHandle.standardOutput
if arguments.count >= 3, arguments[0] == "--output" {
    let outputPath = arguments[1]
    FileManager.default.createFile(atPath: outputPath, contents: nil)
    outputHandle = try FileHandle(forWritingTo: URL(fileURLWithPath: outputPath))
    arguments.removeFirst(2)
}

let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys]

for path in arguments {
    guard let image = NSImage(contentsOfFile: path),
          let data = image.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: data),
          let cgImage = bitmap.cgImage else {
        fputs("Unable to read \(path)\n", stderr)
        exit(1)
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.minimumTextHeight = 0.006
    try VNImageRequestHandler(cgImage: cgImage).perform([request])

    let observations = (request.results ?? []).compactMap { observation -> TextObservation? in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let box = observation.boundingBox
        return TextObservation(
            text: candidate.string,
            x: box.origin.x,
            y: box.origin.y,
            width: box.size.width,
            height: box.size.height
        )
    }
    let record: [String: Any] = [
        "path": path,
        "width": cgImage.width,
        "height": cgImage.height,
        "observations": observations.map {
            ["text": $0.text, "x": $0.x, "y": $0.y, "width": $0.width, "height": $0.height]
        }
    ]
    let output = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys])
    outputHandle.write(output)
    outputHandle.write(Data([0x0A]))
}
