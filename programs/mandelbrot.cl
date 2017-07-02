#pragma OPENCL EXTENSION cl_khr_fp64 : enable

float2 cxMulF(float2 a, float2 b) {
	float2 c;
	c.x = a.x*b.x - a.y*b.y;
	c.y = a.x*b.y + a.y*b.x;
	return c;
}
double2 cxMulD(double2 a, double2 b) {
	double2 c;
	c.x = a.x*b.x - a.y*b.y;
	c.y = a.x*b.y + a.y*b.x;
	return c;
}

int getOuterColor(int iterations) {
	return (int)pow((float)iterations,4)&(0xffffffff);
}

int getInnerColor(float2 cplx) {
	return (abs((int)(cplx.x*0x0fff)) << 16) | abs((int)((cplx.y)*0x0fff));
}

int getAmplitude(int iterations, int max_i){
	return iterations*(0x7fff/max_i);
}

__kernel void img(__global float* x, __global float* y, __global int* out)
{
	const int max_iterations = 1024;
	const float scale = 1;
	
    unsigned int ix = get_global_id(0);
    unsigned int iy = get_global_id(1);
	
	bool inSet = true;
	float2 c = (float2)(x[ix]*scale, y[iy]*scale);
	float2 z = (float2)(0,0);
	
	int i;
	for (i=0; i<max_iterations; i++) {
		z = cxMulF(z,z) + c;
		if ((z.x*z.x + z.y*z.y) > 4) {
			inSet = false;
			break;
		}
	}
	if (!inSet)
		out[ix+get_global_size(0)*iy] = getOuterColor(i);
	else 
		out[ix+get_global_size(0)*iy] = 0;
}

__kernel void snd(__global double* x, __global double* y, __global short* out)
{
	const int max_iterations = 1024;
	const float scale = 1;
	
    unsigned int id = get_global_id(0);
	
	bool inSet = true;
	double2 c = (double2)(x[id]*scale, y[id]*scale);
	double2 z = (double2)(0,0);
	
	int i;
	for (i=0; i<max_iterations; i++) {
		z = cxMulD(z,z) + c;
		if ((z.x*z.x + z.y*z.y) > 4) {
			inSet = false;
			break;
		}
	}
	if (!inSet)
		out[id] = (short)getAmplitude(i,max_iterations);
	else 
		out[id] = 0; //(short)(0x00ff*sin((float)id*2*M_PI/100));
}