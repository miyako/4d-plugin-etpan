#include "windows31j.h"

//we support
//JISX 0213

unsigned short cp932_get_code(unsigned short u)
{
	unsigned short j = 0;
	
	//the standard 11,233 characters + windows oem characters
	j = WINDOWS_31J[u];
	
	return j;
}

void cp932_get_codes(CUTF16String& src, CJISString& jis)
{
	size_t len = src.length();
	jis.resize(len);
	
	for(size_t i = 0; i < len; ++i)
	{
		unsigned short u = src.at(i);
		jis[i] = cp932_get_code(u);
	}
	
}

#pragma mark -

void convert_to_windows_31j_header(const char *header_name,
																 CUTF16String& src,
																 CUTF8String& address,
																 CUTF8String& result)
{
	CJISString chars;
	cp932_get_codes(src, chars);
	
	charset_encode_header(chars, "windows-31j", header_name, src, address, result);
}

void convert_to_windows_31j(CUTF16String& src, CUTF8String& result)
{
	CJISString jis;
	cp932_get_codes(src, jis);

	int len = jis.size();
	
	std::vector<uint8_t>buf((len * 2) + 1);
	size_t pos = 0;
	
//	CUTF8String dst;
	
	for(int i = 0; i < len; ++i)
	{
		if((i % WINDOWS_31J_YIELD_SIZE)==0)
		{
			PA_YieldAbsolute();
		}
		
		unsigned short code = jis.at(i);
		
		switch(code)
		{
			case 0x0000:
				break;
			default:
				if((code >  0x0000) && (code <  0x0080))
				{
//					dst += code;
					buf[pos++] = code;
				}else
				{
//					dst += ((code & 0xFF00) >> 8);
//					dst +=  (code & 0x00FF);
					buf[pos++] = ((code & 0xFF00) >> 8);
					buf[pos++] = (code & 0x00FF);
				}
				break;
		}
	}
	
//	result = dst;
	result = CUTF8String((const uint8_t *)&buf[0], pos);
}
