#include "4DPluginAPI.h"
#include "PrivateTypes.h"
#include "EntryPoints.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <set>

static std::set<PA_Unichar*> strings;
static std::map<PA_Handle, size_t> handles;
static CUTF16String expected;
static int calls;
static int pictureToken;

static void require(bool condition, const char* message)
{
    if (!condition)
    {
        std::fprintf(stderr, "%s\n", message);
        std::exit(1);
    }
}

static PA_Unistring createString(const PA_Unichar* input)
{
    CUTF16String value(input);
    PA_Unistring result = {};
    result.fLength = static_cast<PA_long32>(value.size());
    PA_Unichar* buffer = new PA_Unichar[value.size() + 1];
    std::copy(value.begin(), value.end(), buffer);
    buffer[value.size()] = 0;
    strings.insert(buffer);
    result.fString = buffer;
    return result;
}

static void disposeString(PA_Unistring value)
{
    PA_Unichar* buffer = value.fString;
    if (buffer)
    {
        require(strings.erase(buffer) == 1, "string disposed twice or not owned");
        delete[] buffer;
    }
}

static void host(short selector, EngineBlock* eb)
{
    switch (selector)
    {
        case EX_CREATE_UNISTRING:
            eb->fUniString1 = createString(reinterpret_cast<PA_Unichar*>(eb->fHandle));
            break;
        case EX_DISPOSE_UNISTRING:
            disposeString(eb->fUniString1);
            break;
        case EX_SET_UNISTRING:
            disposeString(eb->fUniString1);
            eb->fUniString1 = createString(reinterpret_cast<PA_Unichar*>(eb->fHandle));
            break;
        case EX_CLEAR_VARIABLE:
        {
            PA_Variable* variable = static_cast<PA_Variable*>(eb->fPtr1);
            if (variable->fType == eVK_Unistring)
                disposeString(variable->uValue.fString);
            else
                require(variable->fType == eVK_Picture, "unexpected variable clear");
            variable->fType = eVK_Undefined;
            break;
        }
        case EX_HANDLE_MANAGER:
        {
            PA_Handle handle = eb->fHandle;
            switch (eb->fParam1)
            {
                case 1:
                    handle = new char*;
                    *handle = new char[eb->fParam2];
                    handles[handle] = eb->fParam2;
                    eb->fHandle = handle;
                    break;
                case 2:
                    require(handles.erase(handle) == 1, "invalid handle disposal");
                    delete[] *handle;
                    delete handle;
                    break;
                case 5:
                    require(handles.count(handle) == 1, "invalid handle lock");
                    eb->fParam3 = reinterpret_cast<sLONG_PTR>(*handle);
                    break;
                case 6:
                    break;
                default:
                    require(false, "unexpected handle operation");
            }
            eb->fError = 0;
            break;
        }
        case EX_CREATE_PICTURE:
            eb->fPicture = &pictureToken;
            eb->fError = 0;
            break;
        case EX_DUPLICATE_PICTURE:
        case EX_DISPOSE_PICTURE:
            break;
        case EX_GET_PICTURE_DATA:
            eb->fUniString1 = {};
            eb->fError = 1;
            break;
        case EX_CONVERT_CHARSET_TO_CHARSET:
        {
            require(eb->fParam2 == eVTC_UTF_8 && eb->fParam4 == eVTC_UTF_16,
                    "unexpected character conversion");
            CFStringRef value = CFStringCreateWithBytes(
                kCFAllocatorDefault, static_cast<const UInt8*>(eb->fPtr1),
                eb->fParam1, kCFStringEncodingUTF8, false);
            require(value != NULL, "invalid UTF-8 conversion input");
            CFIndex length = CFStringGetLength(value);
            require((length + 1) * sizeof(PA_Unichar) <=
                    static_cast<size_t>(eb->fParam3), "conversion buffer too small");
            // Conversion returns bytes, not UTF-16 units or a required terminator.
            std::memset(eb->fPtr2, 0x7f, static_cast<size_t>(eb->fParam3));
            CFStringGetCharacters(value, CFRangeMake(0, length),
                                  static_cast<UniChar*>(eb->fPtr2));
            eb->fParam3 = length * sizeof(PA_Unichar);
            CFRelease(value);
            eb->fError = 0;
            break;
        }
        case EX_EXECUTE_COMMAND_BY_ID:
        {
            require(eb->fParam2 == 2, "unexpected command arity");
            PA_Variable** args = static_cast<PA_Variable**>(eb->fPtr1);
            int index = eb->fParam1 == 678 ? 0 : 1;
            require(eb->fParam1 == 678 || eb->fParam1 == 1002, "unexpected command");
            require(args[index]->fType == eVK_Unistring, "missing command string");
            PA_Unistring value = args[index]->uValue.fString;
            PA_Unichar* buffer = value.fString;
            require(strings.count(buffer) == 1, "command reads freed string");
            require(CUTF16String(value.fString, value.fLength) == expected,
                    "command string content changed");
            if (eb->fParam1 == 678)
                PA_SetPictureVariable(args[1], &pictureToken);
            ++calls;
            eb->fError = 0;
            break;
        }
        default:
            std::fprintf(stderr, "unexpected host selector: %d\n", selector);
            std::exit(1);
    }
}

void PluginMain(PA_long32, PA_PluginParameters) {}

int main(int argc, char** argv)
{
    require(argc == 2, "expected path or copy format case");
    gCall4D = host;
    @autoreleasepool
    {
        C_PICTURE picture;
        const PA_Unichar path[] = {'/', 't', 'm', 'p', '/', 0x65e5, '.', 'p', 'n', 'g', 0};
        C_TEXT text;
        text.setUTF16String(path, 10);
        CUTF8String input;
        text.copyUTF8String(&input);
        CUTF8String original(input);
        const char* format = NULL;
        if (std::strcmp(argv[1], "copy-empty") == 0)
        {
            format = "";
            expected.clear();
        }
        else if (std::strcmp(argv[1], "copy-bmp") == 0)
        {
            format = ".\xe6\x97\xa5";
            const PA_Unichar bmp[] = {'.', 0x65e5, 0};
            expected = CUTF16String(bmp);
        }
        else if (std::strcmp(argv[1], "copy-supplementary") == 0)
        {
            format = ".\xf0\x9f\x98\x80";
            const PA_Unichar supplementary[] = {'.', 0xd83d, 0xde00, 0};
            expected = CUTF16String(supplementary);
        }
        for (int i = 0; i < 100; ++i)
        {
            if (std::strcmp(argv[1], "path") == 0)
            {
                expected = CUTF16String(path);
                picture.fromFileAtPath(&input);
                require(input == original, "caller path input changed");
            }
            else
            {
                PA_Picture copy;
                if (format != NULL)
                {
                    CPicture converter;
                    copy = converter.createCopy(format);
                }
                else if (std::strcmp(argv[1], "copy") == 0)
                {
                    const PA_Unichar png[] = {'.', 'p', 'n', 'g', 0};
                    expected = CUTF16String(png);
                    copy = picture.createCopyPNG();
                }
                else if (std::strcmp(argv[1], "copy-jpg") == 0)
                {
                    const PA_Unichar jpg[] = {'.', 'j', 'p', 'g', 0};
                    expected = CUTF16String(jpg);
                    copy = picture.createCopyJPG();
                }
                else
                {
                    require(std::strcmp(argv[1], "copy-tif") == 0, "unknown test case");
                    const PA_Unichar tif[] = {'.', 't', 'i', 'f', 0};
                    expected = CUTF16String(tif);
                    copy = picture.createCopyTIF();
                }
                require(copy == &pictureToken, "picture result changed");
                PA_DisposePicture(copy);
            }
            require(strings.empty(), "string allocation leaked after command");
            require(handles.empty(), "command argument handle leaked");
        }
    }
    require(calls == 100, "command was not invoked repeatedly");
    return 0;
}
