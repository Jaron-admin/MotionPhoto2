// Test-only. Never imports files into a Photos library. Requires macOS + Xcode CLI tools.
import Foundation
import AppKit
import Photos
import ImageIO
let resources = CommandLine.arguments.dropFirst().map { URL(fileURLWithPath: $0) }
guard resources.count == 2 else { fatalError("Usage: verify_live_photo.swift IMAGE MOV") }
var finished = false
var accepted = false
let request = PHLivePhoto.request(withResourceFileURLs: resources, placeholderImage: nil,
    targetSize: NSSize.zero, contentMode: .aspectFit) { photo, info in
    guard !(info[PHLivePhotoInfoIsDegradedKey] as? Bool ?? false) else { return }
    accepted = photo != nil
    print("Apple final Live Photo recognition:", accepted)
    if let error = info[PHLivePhotoInfoErrorKey] { print("Error:", error) }
    finished = true
}
let deadline = Date().addingTimeInterval(30)
while !finished && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.05)) }
if !finished { PHLivePhoto.cancelRequest(withRequestID: request); print("Timed out") }
exit(accepted ? 0 : 1)
