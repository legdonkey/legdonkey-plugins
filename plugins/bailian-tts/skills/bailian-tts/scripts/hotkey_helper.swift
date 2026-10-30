// 百炼朗读助手:用系统级接口注册全局快捷键(不经过前台 App,Orca、终端里也有效),
// 按下后走和鼠标中键相同的流程:等修饰键松开 → bailian-say --save --hotkey → 模拟 Cmd+C → bailian-say --clipboard。
// 用法:bailian-hotkey <虚拟键码> <状态文件>;修饰键固定为 ⌃⌥⌘。由 tts.py 编译、装成 LaunchAgent。
import Cocoa
import Carbon.HIToolbox

let args = CommandLine.arguments
guard args.count == 3, let keyCode = UInt32(args[1]) else {
    FileHandle.standardError.write("用法:bailian-hotkey <虚拟键码> <状态文件>\n".data(using: .utf8)!)
    exit(64)
}
let statusPath = args[2]
let say = NSHomeDirectory() + "/.local/bin/bailian-say"

// 工作台读这个文件判断:快捷键是否注册成功、有没有辅助功能权限(模拟 Cmd+C 需要)
var lastStatus: [String: Bool] = [:]
func writeStatus(_ s: [String: Bool]) {
    guard s != lastStatus else { return }
    lastStatus = s
    if let data = try? JSONSerialization.data(withJSONObject: s) {
        try? data.write(to: URL(fileURLWithPath: statusPath), options: .atomic)
    }
}

/// 返回 true 表示启动成功(wait 时还要求正常退出);失败原因写到 stderr,即 LaunchAgent 的日志
@discardableResult
func runSay(_ a: [String], wait: Bool) -> Bool {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: say)
    p.arguments = a
    p.standardOutput = FileHandle.nullDevice
    p.standardError = FileHandle.nullDevice  // bailian-say 每次都往 stderr 打模型信息,不进小助手日志
    do { try p.run() } catch {
        FileHandle.standardError.write("启动 \(say) 失败:\(error)\n".data(using: .utf8)!)
        return false
    }
    guard wait else { return true }
    p.waitUntilExit()
    if p.terminationStatus != 0 {
        FileHandle.standardError.write("bailian-say \(a.joined(separator: " ")) 失败,退出码 \(p.terminationStatus)\n".data(using: .utf8)!)
    }
    return p.terminationStatus == 0
}

func pressCopy() {
    let src = CGEventSource(stateID: .hidSystemState)
    for down in [true, false] {
        let e = CGEvent(keyboardEventSource: src, virtualKey: CGKeyCode(kVK_ANSI_C), keyDown: down)
        e?.flags = .maskCommand
        e?.post(tap: .cghidEventTap)
    }
}

let queue = DispatchQueue(label: "bailian-say")  // 串行:连按时按顺序处理
func trigger() {
    queue.async {
        // 不等 ⌃⌥⌘ 松开,模拟的 Cmd+C 会带上它们变成别的组合
        let held: CGEventFlags = [.maskCommand, .maskAlternate, .maskControl, .maskShift]
        var n = 0
        while n < 60 && !CGEventSource.flagsState(.hidSystemState).intersection(held).isEmpty {
            usleep(50_000)
            n += 1
        }
        // --save 没成功(如入口落到不认识 --hotkey 的旧版插件)就停下,免得 --clipboard 拿旧存档覆盖剪贴板
        guard runSay(["--save", "--hotkey"], wait: true) else { return }
        usleep(120_000)
        pressCopy()
        usleep(200_000)
        runSay(["--clipboard"], wait: false)
    }
}

var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
InstallEventHandler(GetApplicationEventTarget(), { _, _, _ -> OSStatus in trigger(); return noErr }, 1, &spec, nil, nil)
var ref: EventHotKeyRef?
let err = RegisterEventHotKey(keyCode, UInt32(cmdKey | optionKey | controlKey), EventHotKeyID(signature: 0x62747473, id: 1),
                              GetApplicationEventTarget(), 0, &ref)
if err != noErr {
    writeStatus(["registered": false, "trusted": AXIsProcessTrusted()])
    FileHandle.standardError.write("快捷键注册失败(\(err)),可能已被其它程序占用\n".data(using: .utf8)!)
    exit(2)
}
// 第一次启动时弹出系统提示,引导用户到「辅助功能」里打开权限;授权后无需重启即生效
let prompt = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
writeStatus(["registered": true, "trusted": AXIsProcessTrustedWithOptions(prompt)])
Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { _ in
    writeStatus(["registered": true, "trusted": AXIsProcessTrusted()])
}
NSApplication.shared.setActivationPolicy(.prohibited)
NSApplication.shared.run()
