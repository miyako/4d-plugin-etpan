#include "shiftjis.h"

//we support
//JISX 0213

unsigned short sjis_get_code(unsigned short u)
{
	unsigned short j = 0;
	
	//the standard 11,233 characters + windows oem characters
	j = JISX_0213[u];
	
	return j;
}

void sjis_get_codes(CUTF16String& src, CJISString& jis)
{
	size_t len = src.length();
	jis.resize(len);
	
	for(size_t i = 0; i < len; ++i)
	{
		unsigned short u = src.at(i);
		jis[i] = sjis_get_code(u);
	}
	
}

#pragma mark -

void convert_to_shift_jis_header(const char *header_name,
																 CUTF16String& src,
																 CUTF8String& address,
																 CUTF8String& result)
{
	CJISString chars;
	sjis_get_codes(src, chars);
	
	charset_encode_header(chars, "shift_jis", header_name, src, address, result);
}

void convert_to_shift_jis(CUTF16String& src, CUTF8String& result)
{
	CJISString jis;
	sjis_get_codes(src, jis);

	int len = jis.size();
	
	std::vector<uint8_t>buf((len * 2) + 1);
	size_t pos = 0;
	
//	CUTF8String dst;
	
	for(int i = 0; i < len; ++i)
	{
		if((i % SHIFT_JIS_YIELD_SIZE)==0)
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
