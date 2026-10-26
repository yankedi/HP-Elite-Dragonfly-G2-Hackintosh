"""Linux i915 ABI *simulation*, never a real fd or ioctl implementation.

Version identity intentionally prevents ANV from treating this model as i915.
All pointer fields refer only to explicit synthetic UserArena allocations.
No method performs open, mmap, ioctl, GPU access, or a hardware submission.
"""
import errno
import json
from pathlib import Path
import threading

ROOT = Path(__file__).resolve().parents[2]


def fail(code, text):
    raise OSError(code, text)


class UserArena:
    """Synthetic copyin/copyout memory, not host virtual addresses."""
    def __init__(self):
        self._next = 0x10000000
        self._ranges = {}
        self._lock = threading.RLock()

    def allocate(self, size, initial=b''):
        if type(size) is not int or not 0 < size <= 1024*1024 or len(initial)>size:
            fail(errno.EINVAL, 'invalid synthetic allocation')
        with self._lock:
            address = self._next
            self._next += (size+15)//16*16+16
            self._ranges[address] = bytearray(initial)+bytearray(size-len(initial))
            return address

    def _locate(self, address, size):
        if type(address) is not int or type(size) is not int or address<0 or size<0 or address+size>2**64:
            fail(errno.EFAULT, 'pointer overflow')
        for base, data in self._ranges.items():
            if base<=address and address-base<=len(data) and size<=len(data)-(address-base):
                return data, address-base
        fail(errno.EFAULT, 'unregistered simulated pointer')

    def read(self, address, size):
        with self._lock:
            data, offset = self._locate(address,size)
            return bytes(data[offset:offset+size])

    def write(self, address, value):
        with self._lock:
            data, offset = self._locate(address,len(value))
            data[offset:offset+len(value)] = value

    def free(self, address):
        with self._lock:
            if address not in self._ranges:
                fail(errno.EFAULT, 'unknown synthetic allocation')
            del self._ranges[address]


class ABI:
    def __init__(self, path=ROOT/'build/uapi-layout-v2/abi.json'):
        self.data = json.loads(Path(path).read_text())
        if self.data['pointer_size']!=8:
            fail(errno.ENOTSUP, 'only recorded x86_64 ABI supported')
        self.by_request = {v['value']:k for k,v in self.data['requests'].items()}

    def fields(self, name):
        return self.data['structs'][self.data['requests'][name]['struct']]

    def pack(self, operation, **values):
        layout = self.fields(operation)
        result = bytearray(layout['size'])
        for key, value in values.items():
            f = layout['fields'][key]
            result[f['offset']:f['offset']+f['size']] = int(value).to_bytes(f['size'],'little',signed=value<0)
        return bytes(result)

    def unpack(self, name, data):
        layout = self.fields(name)
        if not isinstance(data,(bytes,bytearray)) or len(data)!=layout['size']:
            fail(errno.EFAULT, 'ioctl structure size mismatch')
        # drm.h declares timeout_nsec __s64, unlike handles/pointers and flags.
        return {k:int.from_bytes(data[f['offset']:f['offset']+f['size']],'little',
                                signed=(name=='SYNCOBJ_WAIT' and k=='timeout_nsec'))
                for k,f in layout['fields'].items()}


class MockI915:
    """Per-session, lock-protected CPU model handles; never real GPU handles."""
    driver_name = b'GA40_MOCK_ONLY'
    real_gpu = False
    MAX_OBJECTS = 128
    MAX_BYTES = 16*1024*1024

    def __init__(self, abi=None):
        self.abi = abi or ABI()
        self.lock = threading.RLock()
        self.closed = False
        self.next_handle = 1
        self.bos, self.contexts, self.vms, self.syncs = {}, {}, {}, {}
        self.bytes_allocated = 0

    def _id(self):
        if self.next_handle>=2**32:
            fail(errno.ENOSPC, 'model handle space exhausted')
        value = self.next_handle
        self.next_handle += 1
        return value

    def _put(self, table, value):
        if len(table)>=self.MAX_OBJECTS:
            fail(errno.ENOSPC, 'model object quota')
        handle = self._id()
        table[handle] = value
        return handle

    def _get(self, table, handle):
        if handle not in table:
            fail(errno.ENOENT, 'unknown per-session model handle')
        return table[handle]

    def _live(self):
        if self.closed:
            fail(errno.EBADF, 'closed model session')

    def require_real_anv_device(self):
        fail(errno.ENODEV, 'GA40 CPU model is not an i915 DRM device')

    def ioctl(self, request, data, arena=None):
        with self.lock:
            self._live()
            if type(request) is not int or request not in self.abi.by_request:
                fail(errno.ENOTTY, 'unknown Linux request, including Darwin encodings')
            name = self.abi.by_request[request]
            values = self.abi.unpack(name,data)
            # No unimplemented operation is allowed to return success.
            if name in {'I915_GETPARAM','I915_QUERY','I915_GEM_MMAP_OFFSET','I915_GEM_EXECBUFFER2'}:
                fail(errno.ENOTSUP, 'no real query, BO mapping, GPU VA, or submission in model')
            if values.get('pad',0) or values.get('extensions',0):
                fail(errno.EINVAL, 'unsupported padding or extension chain')
            if values.get('deadline_nsec',0):
                fail(errno.EINVAL, 'deadline hints not modeled')
            if name=='VERSION':
                values.update(version_major=0,version_minor=0,version_patchlevel=0)
                for key,text in [('name',self.driver_name),('date',b'20261020'),('desc',b'CPU-only explicit ABI simulation')]:
                    count = min(values[key+'_len'],len(text))
                    if count:
                        if not values[key] or arena is None:
                            fail(errno.EFAULT,'null or absent synthetic user memory for copyout')
                        arena.write(values[key],text[:count])
                    values[key+'_len'] = len(text)
            elif name=='GET_CAP':
                if values['capability']!=self.abi.data['constants']['DRM_CAP_PRIME']:
                    fail(errno.EINVAL,'capability not advertised by this model')
                values['value']=0
            elif name=='I915_GEM_CREATE':
                size = values['size']
                if not size or size>self.MAX_BYTES: fail(errno.EINVAL,'BO size invalid')
                size=(size+4095)//4096*4096
                if size>self.MAX_BYTES-self.bytes_allocated: fail(errno.ENOMEM,'model byte quota')
                values['handle']=self._put(self.bos,bytearray(size))
                values['size']=size
                self.bytes_allocated+=size
            elif name=='GEM_CLOSE':
                self.bytes_allocated-=len(self._get(self.bos,values['handle']))
                del self.bos[values['handle']]
            elif name=='I915_GEM_CONTEXT_CREATE_EXT':
                if values['flags']: fail(errno.EINVAL,'context flags unsupported')
                values['ctx_id']=self._put(self.contexts,{'kind':'CPU_MODEL_ONLY'})
            elif name=='I915_GEM_CONTEXT_DESTROY':
                self._get(self.contexts,values['ctx_id']); del self.contexts[values['ctx_id']]
            elif name=='I915_GEM_VM_CREATE':
                if values['flags']: fail(errno.EINVAL,'VM flags unsupported')
                values['vm_id']=self._put(self.vms,{'gpu_va_available':False})
            elif name=='I915_GEM_VM_DESTROY':
                if values['flags']: fail(errno.EINVAL,'VM flags unsupported')
                self._get(self.vms,values['vm_id']); del self.vms[values['vm_id']]
            elif name=='SYNCOBJ_CREATE':
                bit=self.abi.data['constants']['SYNCOBJ_SIGNALED']
                if values['flags']&~bit: fail(errno.EINVAL,'sync flags unsupported')
                values['handle']=self._put(self.syncs,bool(values['flags']&bit))
            elif name=='SYNCOBJ_DESTROY':
                self._get(self.syncs,values['handle']); del self.syncs[values['handle']]
            elif name in {'SYNCOBJ_SIGNAL','SYNCOBJ_RESET','SYNCOBJ_WAIT'}:
                count=values['count_handles']; ptr=values['handles']
                if not 0<count<=64 or ptr%4: fail(errno.EINVAL,'count/alignment invalid')
                if arena is None: fail(errno.EFAULT,'no synthetic user memory')
                raw=arena.read(ptr,count*4)
                handles=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
                states=[self._get(self.syncs,h) for h in handles] # validate all before mutation
                if name=='SYNCOBJ_WAIT':
                    bit=self.abi.data['constants']['WAIT_ALL']
                    if values['flags']&~bit: fail(errno.EINVAL,'wait flags unsupported')
                    if not (all(states) if values['flags']&bit else any(states)):
                        fail(errno.ETIME,'CPU model fence unsignaled; no batch executed')
                    values['first_signaled']=next(i for i,v in enumerate(states) if v)
                else:
                    for h in handles: self.syncs[h]=name=='SYNCOBJ_SIGNAL'
            else:
                fail(errno.ENOTTY,'unmodeled request')
            return self.abi.pack(name,**values)

    def cpu_bo_write(self, handle, offset, data):
        """Model-only backing store access; explicitly NOT BO mmap."""
        with self.lock:
            self._live(); bo=self._get(self.bos,handle)
            if type(offset) is not int or offset<0 or offset>len(bo) or len(data)>len(bo)-offset:
                fail(errno.EINVAL,'CPU model range invalid')
            bo[offset:offset+len(data)]=data

    def cpu_bo_read(self, handle, offset, size):
        with self.lock:
            self._live(); bo=self._get(self.bos,handle)
            if type(offset) is not int or type(size) is not int or offset<0 or size<0 or offset>len(bo) or size>len(bo)-offset:
                fail(errno.EINVAL,'CPU model range invalid')
            return bytes(bo[offset:offset+size])

    def close(self):
        with self.lock:
            self._live()
            self.bos.clear(); self.contexts.clear(); self.vms.clear(); self.syncs.clear()
            self.bytes_allocated=0; self.closed=True
