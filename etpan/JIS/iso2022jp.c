#include "iso2022jp.h"

//JISX 0208 japanese
//JISX 0201 ASCII + kana (62) + yen + overline

unsigned short jis_get_code(unsigned short u)
{
	unsigned short j = 0;
	
	//the standard 6,879 characters + windows oem characters
	j = ISO_2022_JISX_0208[u];
	
	return j;
}

void jis_get_codes(CUTF16String& src, CJISString& jis)
{
	size_t len = src.length();
	jis.resize(len);
	
	for(size_t i = 0; i < len; ++i)
	{
		unsigned short u = src.at(i);
		jis[i] = jis_get_code(u);
	}

}

#pragma mark -

void convert_to_iso_2022_jp_header(const char *header_name,
																	 CUTF16String& src,
																	 CUTF8String& address,
																	 CUTF8String& result)
{
	CUTF8String name = (const uint8_t *)(header_name ? header_name : "");

	CJISString jis;
	jis_get_codes(src, jis);

	ISO_2022_STATE state = ISO_2022_STATE_ASCII;

	int len = jis.size();
	int before_last = len > 0 ? len-1 : 0;
	
	CUTF8String dst;

	int line_length = name.length() + 2;// ": "
	int max_line_length = ISO_2022_MAX_LINE_LENGTH_FOR_HEADER - line_length;
	
	for(int i = 0; i < len; ++i)
	{
		if((i % ISO_2022_YIELD_SIZE)==0)
		{
			PA_YieldAbsolute();
		}
		
		unsigned short code = jis.at(i);
		
		switch(code)
		{
			case 0x0000:
				break;
				
			case 0x007E:
			case 0x005C:
			{
				if(state == ISO_2022_STATE_ASCII)
				{
					if(line_length < (max_line_length - 23))// BEFORE (16), ASCII(5), AFTER (2)
					{
						dst += Q_ISO_2022_BEFORE;// 16
						line_length += 17;
					}else
					{
						dst += Q_ISO_2022_FLOW;// (2) 1
						dst += Q_ISO_2022_BEFORE;// 16
						line_length = 17;
						max_line_length = ISO_2022_MAX_LINE_LENGTH_FOR_HEADER - line_length - 7;//ASCII (5), AFTER (2)
					}
				}
				if(state != ISO_2022_STATE_ROMAN)
				{
					state = ISO_2022_STATE_ROMAN;
					dst += Q_ISO_2022_ESC_JISX_0201_ROMAN;// 5
					line_length += 5;
				}
				dst += code;
				line_length++;
			}
				break;
			default:
				if((code >  0x0000) && (code <  0x0080))
				{
					if(state != ISO_2022_STATE_ASCII)
					{
						dst += Q_ISO_2022_ESC_ASCII;// 5
						dst += Q_ISO_2022_AFTER;// 2
						line_length += 7;
						
						if(line_length >= max_line_length)
						{
							dst += Q_ISO_2022_FLOW;// (2) 1
							line_length = 1;
							max_line_length = ISO_2022_MAX_LINE_LENGTH_FOR_HEADER - line_length;
						}
						state = ISO_2022_STATE_ASCII;
					}
					dst += code;
					line_length++;
					if((code == 0x000A) && (i > 0) && (jis.at(i-1) == 0x000D))
					{
						dst += ' ';
						line_length = 1;
						max_line_length = ISO_2022_MAX_LINE_LENGTH_FOR_HEADER - line_length;
					}
				}else
					if((code >= 0x00A1) && (code <= 0x00DF))
					{
						if(state == ISO_2022_STATE_ASCII)
						{
							if(line_length < (max_line_length - 23))// BEFORE (16), ASCII(5), AFTER (2)
							{
								dst += Q_ISO_2022_BEFORE;// 16
								line_length += 17;
							}else
							{
								dst += Q_ISO_2022_FLOW;// (2) 1
								dst += Q_ISO_2022_BEFORE;// 16
								line_length = 18;
								max_line_length = ISO_2022_MAX_LINE_LENGTH_FOR_HEADER - line_length - 7;//ASCII (5), AFTER (2)
							}
						}
						if(state != ISO_2022_STATE_KATAKANA)
						{
							state = ISO_2022_STATE_KATAKANA;
							dst += Q_ISO_2022_ESC_JISX_0201_KATAKANA;// 5
							line_length += 5;
						}
						dst += (code & 0x007F);
						line_length++;
					}else
					{
						if(state == ISO_2022_STATE_ASCII)
						{
							if(line_length < (max_line_length - 23))// BEFORE (16), ASCII(5), AFTER (2)
							{
								dst += Q_ISO_2022_BEFORE;// 16
								line_length += 17;
							}else
							{
								dst += Q_ISO_2022_FLOW;// (2) 1
								dst += Q_ISO_2022_BEFORE;// 16
								line_length = 18;
								max_line_length = ISO_2022_MAX_LINE_LENGTH_FOR_HEADER - line_length - 7;//ASCII (5), AFTER (2)
							}
						}
						if(state != ISO_2022_STATE_JIS)
						{
							state = ISO_2022_STATE_JIS;
							dst += Q_ISO_2022_ESC_JISX_0208_1983;// 5
							line_length += 5;
						}
						dst += ((code & 0xFF00) >> 8);
						dst +=  (code & 0x00FF);
						line_length += 2;
					}
				break;
		}
		
		if(line_length >= max_line_length)
		{
			if(state != ISO_2022_STATE_ASCII)
			{
				state = ISO_2022_STATE_ASCII;
				dst += Q_ISO_2022_ESC_ASCII;// 5
				dst += Q_ISO_2022_AFTER;// 2
			}
			dst += Q_ISO_2022_FLOW;// (2) 1
			line_length = 1;
			max_line_length = ISO_2022_MAX_LINE_LENGTH_FOR_HEADER - line_length;
		}
		if(i == before_last)
		{
			if(state != ISO_2022_STATE_ASCII)
			{
				state = ISO_2022_STATE_ASCII;
				dst += Q_ISO_2022_ESC_ASCII;// 5
				dst += Q_ISO_2022_AFTER;// 2
				line_length += 7;
			}
			
			CUTF8String a;
			if(address.length())
			{
				a += ' ';
				a += '<';
				a += address;
				a += '>';
				for(int j = 0; j < a.length(); ++j)
				{
					if(line_length >= max_line_length)
					{
						dst += Q_ISO_2022_FLOW;// (2) 1
						line_length = 1;
						max_line_length = ISO_2022_MAX_LINE_LENGTH_FOR_HEADER - line_length;
					}
					dst += a.at(j);
				}
			}
		}
	}
	result = dst;
}

void convert_to_iso_2022_jp_header_b(const char *header_name,
															CUTF16String& src,
															CUTF8String& address,
															CUTF8String& result)
{
	//raw (no soft-breaks) iso-2022 for double encoding with base64
	const char b64_table[65] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
	CUTF8String name = (const uint8_t *)(header_name ? header_name : "");
	CUTF8String encoding_name = (const uint8_t *)"iso-2022-jp";
	CUTF8String STRING_BEFORE = (const uint8_t *)"=?";
	STRING_BEFORE += encoding_name;
	STRING_BEFORE += (const uint8_t *)"?B?";
	size_t STRING_BEFORE_LENGTH = STRING_BEFORE.length();
	CUTF8String STRING_AFTER = (const uint8_t *)"?=";
	size_t STRING_AFTER_LENGTH = STRING_AFTER.length();
	CUTF8String STRING_FLOW = (const uint8_t *)"\r\n ";
	size_t STRING_FLOW_LENGTH = 1;
	
	CJISString jis;
	jis_get_codes(src, jis);
	
	ISO_2022_STATE state = ISO_2022_STATE_ASCII;
	
	int len = jis.size();
	int before_last = len > 0 ? len-1 : 0;
	
	int pos = name.length() + 2;// ": "
	int max_line_length = MAX_LINE_LENGTH_FOR_HEADER - 5 - encoding_name.length() - pos - 3;// =??B?, ?=, ASCII
	
	int bits_collected = 0;
	unsigned int accumulator = 0;
	
	CUTF8String dst;
	
	CUTF8String buffer;
	
	for(int i = 0; i < len; ++i)
	{
		if((i % ISO_2022_YIELD_SIZE)==0)
		{
			PA_YieldAbsolute();
		}
		
		unsigned short code = jis.at(i);
		
		switch(code)
		{
			case 0x0000:
				break;
				
			case 0x007E:
			case 0x005C:
			{
				if(state != ISO_2022_STATE_ROMAN)
				{
					state = ISO_2022_STATE_ROMAN;
//					dst += ISO_2022_ESC_JISX_0201_ROMAN;
					buffer += ISO_2022_ESC_JISX_0201_ROMAN;
//					line_length += 3;
				}
//				dst += code;
				buffer += code;
//				line_length++;
			}
				break;
			default:
				if((code >  0x0000) && (code <  0x0080))
				{
					if(state != ISO_2022_STATE_ASCII)
					{
						state = ISO_2022_STATE_ASCII;
//						dst += ISO_2022_ESC_ASCII;
						buffer += ISO_2022_ESC_ASCII;
//						line_length += 3;
					}
//					dst += code;
					buffer += code;
//					line_length++;
//					if((code == 0x000D) && (i < before_last) && (jis.at(i+1) == 0x000A))
//					{
//						line_length = 0;
//					}
				}else
					if((code >= 0x00A1) && (code <= 0x00DF))
					{
						if(state != ISO_2022_STATE_KATAKANA)
						{
							state = ISO_2022_STATE_KATAKANA;
//							dst += ISO_2022_ESC_JISX_0201_KATAKANA;
							buffer += ISO_2022_ESC_JISX_0201_KATAKANA;
//							line_length += 3;
						}
//						dst += (code & 0x007F);
						buffer += (code & 0x007F);
//						line_length++;
					}else
					{
						
						if(state != ISO_2022_STATE_JIS)
						{
							state = ISO_2022_STATE_JIS;
//							dst += ISO_2022_ESC_JISX_0208_1983;
							buffer += ISO_2022_ESC_JISX_0208_1983;
//							line_length += 3;
						}
						
//						dst += ((code & 0xFF00) >> 8);
//						dst +=  (code & 0x00FF);
						buffer += ((code & 0xFF00) >> 8);
						buffer +=  (code & 0x00FF);
//						line_length += 2;
					}
				break;
		}
		
//		if(line_length > ISO_2022_MAX_LINE_LENGTH)
//		{
//			if(state != ISO_2022_STATE_ASCII)
//			{
//				state = ISO_2022_STATE_ASCII;
//				dst += ISO_2022_ESC_ASCII;
//			}
//			dst += ISO_2022_FLOW;
//			line_length = 0;
//		}
		
//		if(i == before_last)
//		{
//			if(state != ISO_2022_STATE_ASCII)
//			{
//				state = ISO_2022_STATE_ASCII;
//				dst += ISO_2022_ESC_ASCII;
//				dst += ISO_2022_FLOW;
//				buffer += ISO_2022_ESC_ASCII;
//				buffer += ISO_2022_FLOW;
//			}
//		}
		
		if(((buffer.length() / 3) * 4) >= max_line_length)
		{
			if(state != ISO_2022_STATE_ASCII)
			{
				state = ISO_2022_STATE_ASCII;
				//				dst += ISO_2022_ESC_ASCII;
				//				dst += ISO_2022_FLOW;
				buffer += ISO_2022_ESC_ASCII;
				//				buffer += ISO_2022_FLOW;
			}
			int buf_len = 0;
			dst += STRING_BEFORE;
			pos += STRING_BEFORE_LENGTH;
			bits_collected = 0;
			accumulator = 0;
			
			for(int j = 0; j < buffer.length();++j)
			{
				accumulator = (accumulator << 8) | (buffer.at(j) & 0xffu);
				bits_collected += 8;
				while (bits_collected >= 6)
				{
					bits_collected -= 6;
					dst += b64_table[(accumulator >> bits_collected) & 0x3fu];
					buf_len++;
					pos++;
				}
			}
			
			if (bits_collected > 0)
			{
				accumulator <<= 6 - bits_collected;
				dst += b64_table[accumulator & 0x3fu];
				buf_len++;
				pos++;
			}
			
			switch(buf_len % 4)
			{
				case 1:
					dst += CUTF8String((const uint8_t *)"===");// 3
					pos += 3;
					break;
				case 2:
					dst += CUTF8String((const uint8_t *)"==");// 2
					pos += 2;
					break;
				case 3:
					dst += CUTF8String((const uint8_t *)"=");// 1
					pos += 1;
					break;
			}
			
			dst += STRING_AFTER;
			pos += STRING_AFTER_LENGTH;
			
			if(i != before_last)
			{
				dst += STRING_FLOW;// (2) 1
				pos = STRING_FLOW_LENGTH;
				max_line_length = MAX_LINE_LENGTH_FOR_HEADER - 5 - encoding_name.length();// =??B?, ?=
			}
			
			buffer = CUTF8String((const uint8_t *)"");
		}
	}//for
	
	if(buffer.length())
	{
		if(state != ISO_2022_STATE_ASCII)
		{
			state = ISO_2022_STATE_ASCII;
			//				dst += ISO_2022_ESC_ASCII;
			//				dst += ISO_2022_FLOW;
			buffer += ISO_2022_ESC_ASCII;
			//				buffer += ISO_2022_FLOW;
		}
		int buf_len = 0;
		dst += STRING_BEFORE;
		pos += STRING_BEFORE_LENGTH;
		bits_collected = 0;
		accumulator = 0;
		
		for(int j = 0; j < buffer.length();++j)
		{
			accumulator = (accumulator << 8) | (buffer.at(j) & 0xffu);
			bits_collected += 8;
			while (bits_collected >= 6)
			{
				bits_collected -= 6;
				dst += b64_table[(accumulator >> bits_collected) & 0x3fu];
				buf_len++;
				pos++;
			}
		}
		
		if (bits_collected > 0)
		{
			accumulator <<= 6 - bits_collected;
			dst += b64_table[accumulator & 0x3fu];
			buf_len++;
			pos++;
		}
		
		switch(buf_len % 4)
		{
			case 1:
				dst += CUTF8String((const uint8_t *)"===");
				pos += 3;
				break;
			case 2:
				dst += CUTF8String((const uint8_t *)"==");
				pos += 2;
				break;
			case 3:
				dst += CUTF8String((const uint8_t *)"=");
				pos ++;
				break;
		}
		
		dst += STRING_AFTER;
		pos += STRING_AFTER_LENGTH;
	}
	
	CUTF8String a;
	if(address.length())
	{
		if(len)
		{
			a += ' ';
			a += '<';
			a += address;
			a += '>';
			pos = 3 + address.length();
		}else
		{
			a = address;
			pos = 0;
		}
		
		for(int j = 0; j < a.length(); ++j)
		{
			pos += 1;
			if(pos >= max_line_length)
			{
				dst += STRING_FLOW;// (2) 1
				pos = STRING_FLOW_LENGTH;
			}
			dst += a.at(j);
		}
	}
	
	result = dst;
}

void convert_to_iso_2022_jp(CUTF16String& src, CUTF8String& result)
{
	CJISString jis;
	jis_get_codes(src, jis);

	ISO_2022_STATE state = ISO_2022_STATE_ASCII;
	
	int line_length = 0;
	int len = jis.size();
	int before_last = len > 0 ? len-1 : 0;
	
	CUTF8String dst;
	
	for(int i = 0; i < len; ++i)
	{
		if((i % ISO_2022_YIELD_SIZE)==0)
		{
			PA_YieldAbsolute();
		}
		
		unsigned short code = jis.at(i);
		
		switch(code)
		{
			case 0x0000:
				break;
				
			case 0x007E:
			case 0x005C:
				{
					if(state != ISO_2022_STATE_ROMAN)
					{
						state = ISO_2022_STATE_ROMAN;
						dst += ISO_2022_ESC_JISX_0201_ROMAN;
						line_length += 3;
					}
					dst += code;
					line_length++;
				}
				break;
			default:
				if((code >  0x0000) && (code <  0x0080))
				{
					if(state != ISO_2022_STATE_ASCII)
					{
						state = ISO_2022_STATE_ASCII;
						dst += ISO_2022_ESC_ASCII;
						line_length += 3;
					}
					dst += code;
					line_length++;
					if((code == 0x000D) && (i < before_last) && (jis.at(i+1) == 0x000A))
					{
						line_length = 0;
					}
				}else
				if((code >= 0x00A1) && (code <= 0x00DF))
				{
					if(state != ISO_2022_STATE_KATAKANA)
					{
						state = ISO_2022_STATE_KATAKANA;
						dst += ISO_2022_ESC_JISX_0201_KATAKANA;
						line_length += 3;
					}
					dst += (code & 0x007F);
					line_length++;
				}else
				{

					if(state != ISO_2022_STATE_JIS)
					{
						state = ISO_2022_STATE_JIS;
						dst += ISO_2022_ESC_JISX_0208_1983;
						line_length += 3;
					}
					
					dst += ((code & 0xFF00) >> 8);
					dst +=  (code & 0x00FF);
					line_length += 2;
				}
				break;
		}
		
		if(line_length > ISO_2022_MAX_LINE_LENGTH)
		{
			if(state != ISO_2022_STATE_ASCII)
			{
				state = ISO_2022_STATE_ASCII;
				dst += ISO_2022_ESC_ASCII;
			}
			dst += ISO_2022_FLOW;
			line_length = 0;
		}
		if(i == before_last)
		{
			if(state != ISO_2022_STATE_ASCII)
			{
				state = ISO_2022_STATE_ASCII;
				dst += ISO_2022_ESC_ASCII;
				dst += ISO_2022_FLOW;
			}
		}
	}
	result = dst;
}
















