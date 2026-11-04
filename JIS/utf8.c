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
	
	int pos = name.length() + 2;// ": "
	int max_line_length = UTF8_MAX_LINE_LENGTH - 5 - encoding_name.length() - pos;// =??B?, ?=
	
	int bits_collected = 0;
	unsigned int accumulator = 0;
	
	CUTF8String dst;
	
	CUTF8String buffer;
	std::vector<uint8_t> buf(UTF8_MAX_LINE_LENGTH);
	int buf_pos = 0;
	
	//each encoded word must hold whole characters (RFC 2047 5.3):
	//collect one complete UTF-8 sequence at a time, and flush the buffer
	//before a character that would make the encoded word too long
	for(int i = 0; i < len; ++i)
	{
		if((i % UTF8_YIELD_SIZE)==0)
		{
			PA_YieldAbsolute();
		}
		
		uint8_t code = src.at(i);
		
		int seq_len;
		if(code < 0x80)
		{
			seq_len = 1;
		}else if((code & 0xE0) == 0xC0)
		{
			seq_len = 2;
		}else if((code & 0xF0) == 0xE0)
		{
			seq_len = 3;
		}else if((code & 0xF8) == 0xF0)
		{
			seq_len = 4;
		}else
		{
			continue;//stray continuation byte or invalid lead byte
		}
		
		if((i + seq_len) > len)
		{
			break;//truncated sequence at the end
		}
		
		bool valid = true;
		for(int k = 1; k < seq_len; ++k)
		{
			if((src.at(i + k) & 0xC0) != 0x80)
			{
				valid = false;
				break;
			}
		}
		if(!valid)
		{
			continue;//drop the lead byte, resync on the next one
		}
		
		//base64 length of the buffer with this character added
		if((buf_pos) && ((((buf_pos + seq_len + 2) / 3) * 4) > max_line_length))
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
				case 2:
					dst += CUTF8String((const uint8_t *)"==");
					pos += 2;
					break;
				case 3:
					dst += CUTF8String((const uint8_t *)"=");
					pos += 1;
					break;
			}
			
			dst += STRING_AFTER;
			pos += STRING_AFTER_LENGTH;
			
			//more characters follow: fold the line
			dst += STRING_FLOW;
			pos = STRING_FLOW_LENGTH;
			//an encoded word is at most 75 characters (RFC 2047 2): " =?utf-8?B?" + text + "?="
			max_line_length = 75 - (int)(STRING_BEFORE_LENGTH + STRING_AFTER_LENGTH) - STRING_FLOW_LENGTH;
			
			buffer = CUTF8String((const uint8_t *)"");
			buf_pos = 0;
		}
		
		if((size_t)(buf_pos + seq_len) > buf.size())
		{
			buf.resize(buf_pos + seq_len);
		}
		for(int k = 0; k < seq_len; ++k)
		{
			buf[buf_pos++] = src.at(i + k);
		}
		i += (seq_len - 1);
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
