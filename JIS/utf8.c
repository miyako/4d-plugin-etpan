#include "utf8.h"

void convert_to_utf8_header(const char *header_name,
																 CUTF8String& src,
																 CUTF8String& address,
																 CUTF8String& result)
{
	const char b64_table[65] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
	
	CUTF8String name = (const uint8_t *)(header_name ? header_name : "");
	CUTF8String encoding_name = (const uint8_t *)"utf-8";
	CUTF8String STRING_BEFORE = (const uint8_t *)"=?";
	STRING_BEFORE += encoding_name;
	STRING_BEFORE += (const uint8_t *)"?B?";
	size_t STRING_BEFORE_LENGTH = STRING_BEFORE.length();
	CUTF8String STRING_AFTER = (const uint8_t *)"?=";
	size_t STRING_AFTER_LENGTH = STRING_AFTER.length();
	CUTF8String STRING_FLOW = (const uint8_t *)"\r\n ";
	size_t STRING_FLOW_LENGTH = 1;
	
	int len = src.size();
	int before_last = len > 0 ? len-1 : 0;
	
	int pos = name.length() + 2;// ": "
	int max_line_length = UTF8_MAX_LINE_LENGTH - 5 - encoding_name.length() - pos;// =??B?, ?=
	
	int bits_collected = 0;
	unsigned int accumulator = 0;
	
	CUTF8String dst;
	
	CUTF8String buffer;
	std::vector<uint8_t> buf(UTF8_MAX_LINE_LENGTH);
	int buf_pos = 0;
	
	for(int i = 0; i < len; ++i)
	{
		if((i % UTF8_YIELD_SIZE)==0)
		{
			PA_YieldAbsolute();
		}
		
		//UTF-8
		uint8_t code = src.at(i);
		
		if((code & 0xFC) && (i < (len-5)))// 6
		{
			buf[buf_pos++] = code;
			buf[buf_pos++] = src.at(++i);
			buf[buf_pos++] = src.at(++i);
			buf[buf_pos++] = src.at(++i);
			buf[buf_pos++] = src.at(++i);
			buf[buf_pos++] = src.at(++i);
		}else if((code & 0xF8) && (i < (len-4)))// 5
		{
			buffer += code;
			buf[buf_pos++] = src.at(++i);
			buf[buf_pos++] = src.at(++i);
			buf[buf_pos++] = src.at(++i);
			buf[buf_pos++] = src.at(++i);
		}else if((code & 0xF0) && (i < (len-3)))// 4
		{
			buffer += code;
			buf[buf_pos++] = src.at(++i);
			buf[buf_pos++] = src.at(++i);
			buf[buf_pos++] = src.at(++i);
		}else if((code & 0xE0) && (i < (len-2)))// 3
		{
			buf[buf_pos++] = code;
			buf[buf_pos++] = src.at(++i);
			buf[buf_pos++] = src.at(++i);
		}else if((code & 0xC0) && (i < (len-1)))// 2
		{
			buf[buf_pos++] = code;
			buf[buf_pos++] = src.at(++i);
		}else if(code <= 0x7F)// 1
		{
			buf[buf_pos++] = code;
		}else
		{
			continue;
		}

		if(((buf_pos / 3) * 4) >= max_line_length)
		{
			buffer = CUTF8String(&buf[0], buf_pos);
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
			buf_pos = 0;
		}
	}//for
	
	if(buf_pos)
	{
		buffer = CUTF8String(&buf[0], buf_pos);
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
