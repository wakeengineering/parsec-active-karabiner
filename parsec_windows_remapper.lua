-- Hide Hammerspoon from the Dock (runs silently in background)
hs.dockIcon(false)

local eventtap = hs.eventtap
local eventTypes = eventtap.event.types

-- Start state (Global)
_G.parsec_guest_active = false

-- -------------------------------------------------------------
-- 1. KEY SWAPPING LOGIC (Globalized to prevent GC)
-- -------------------------------------------------------------
_G.parsecKeySwapper = eventtap.new({
    eventTypes.keyDown,
    eventTypes.keyUp,
    eventTypes.flagsChanged
}, function(event)
    -- Only swap if a guest is actively connected
    if not _G.parsec_guest_active then 
        return false 
    end
    
    local flags = event:getFlags()
    
    -- Swap Command (cmd) and Option (alt)
    local hasCmd = flags.cmd
    local hasAlt = flags.alt
    
    flags.cmd = hasAlt
    flags.alt = hasCmd
    
    event:setFlags(flags)
    
    -- return false to let the modified event pass through to the OS
    return false 
end)

_G.parsecKeySwapper:start()

-- -------------------------------------------------------------
-- 2. PARSEC MONITORING LOGIC (Globalized to prevent GC)
-- -------------------------------------------------------------

-- Locate Parsec log file
local homeDir = os.getenv("HOME")
local paths = {
    homeDir .. "/.parsec/log.txt",
    "/Users/Shared/.parsec/log.txt"
}

local logPath = nil
for _, path in ipairs(paths) do
    local f = io.open(path, "r")
    if f then
        f:close()
        logPath = path
        break
    end
end

local function checkLogForConnection()
    if not logPath then 
        print("[Parsec Monitor] ERROR: Log path not found.")
        return 
    end
    
    -- Read the last 50 lines of the log
    local handle = io.popen("tail -n 50 " .. string.format("%q", logPath))
    local result = handle:read("*a")
    handle:close()
    
    -- Initialize to the CURRENT state instead of defaulting to false
    local isConnected = _G.parsec_guest_active
    
    for line in result:gmatch("[^\r\n]+") do
        -- Check for disconnection events first
        if line:find("disconnected%.") or line:find("Connection closed") or line:find("kick") then
            isConnected = false
        -- Check for connection events with a leading space
        elseif line:find("%sconnected%.") then
            isConnected = true
        end
    end
    
    -- Only print and update if the state has actually changed
    if _G.parsec_guest_active ~= isConnected then
        _G.parsec_guest_active = isConnected
        print("[Parsec Monitor] Guest connection state changed! Active = " .. tostring(_G.parsec_guest_active))
    end
end

-- Watch the .parsec directory for changes to log.txt (Globalized)
_G.parsecWatcher = nil
if logPath then
    print("[Parsec Monitor] Successfully targeting Parsec log at: " .. logPath)
    local parsecDir = logPath:match("(.*/)")
    _G.parsecWatcher = hs.pathwatcher.new(parsecDir, function(files)
        for _, file in ipairs(files) do
            if file:match("log%.txt$") then
                checkLogForConnection()
                break
            end
        end
    end):start()
    
    -- Sync initial state
    checkLogForConnection()
else
    print("[Parsec Monitor] ERROR: Parsec log.txt not found in expected directories.")
end