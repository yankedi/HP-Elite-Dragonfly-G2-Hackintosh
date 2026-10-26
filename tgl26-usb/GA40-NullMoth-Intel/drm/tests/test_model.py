import concurrent.futures
import errno
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'mock'))
from i915_model import ABI, MockI915, UserArena


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.abi=ABI()
    def setUp(self): self.dev=MockI915(self.abi); self.arena=UserArena()
    def call(self,operation,**values):
        raw=self.abi.pack(operation,**values)
        return self.abi.unpack(operation,self.dev.ioctl(self.abi.data['requests'][operation]['value'],raw,self.arena))
    def error(self,code,fn,*args,**kwargs):
        with self.assertRaises(OSError) as cm: fn(*args,**kwargs)
        self.assertEqual(cm.exception.errno,code)

    def test_layout_exact_x64(self):
        expected={'drm_version':64,'drm_get_cap':16,'drm_i915_getparam':16,
                  'drm_i915_gem_create':16,'drm_gem_close':8,
                  'drm_i915_gem_context_create_ext':16,'drm_i915_gem_vm_control':16,
                  'drm_syncobj_wait':40,'drm_i915_gem_execbuffer2':64}
        for name,size in expected.items(): self.assertEqual(self.abi.data['structs'][name]['size'],size)
        self.assertEqual(self.abi.data['structs']['drm_i915_getparam']['fields']['value']['offset'],8)
        self.assertEqual(self.abi.data['requests']['I915_GEM_CREATE']['value'],0xc010645b)
        self.assertEqual(self.abi.data['structs']['drm_syncobj_wait']['fields']['deadline_nsec']['offset'],32)

    def test_identity_rejects_anv(self):
        ptr=self.arena.allocate(64)
        out=self.call('VERSION',name_len=64,name=ptr)
        self.assertEqual(self.arena.read(ptr,out['name_len']),b'GA40_MOCK_ONLY')
        self.assertNotEqual(self.dev.driver_name,b'i915')
        self.error(errno.ENODEV,self.dev.require_real_anv_device)
        self.assertFalse(self.dev.real_gpu)

    def test_version_length_and_pointer_rules(self):
        ptr=self.arena.allocate(3)
        out=self.call('VERSION',name_len=3,name=ptr)
        self.assertEqual(out['name_len'],len(self.dev.driver_name))
        self.assertEqual(self.arena.read(ptr,3),b'GA4')
        self.error(errno.EFAULT,self.call,'VERSION',name=0xfffffff0,name_len=8)
        self.assertEqual(self.call('VERSION')['name_len'],len(self.dev.driver_name))

    def test_bo_rounding_backing_and_lifetime(self):
        out=self.call('I915_GEM_CREATE',size=1)
        self.assertEqual(out['size'],4096); h=out['handle']
        self.dev.cpu_bo_write(h,4092,b'last')
        self.assertEqual(self.dev.cpu_bo_read(h,4092,4),b'last')
        self.error(errno.EINVAL,self.dev.cpu_bo_write,h,4094,b'overflow')
        self.call('GEM_CLOSE',handle=h)
        self.error(errno.ENOENT,self.call,'GEM_CLOSE',handle=h)
        self.assertEqual(self.dev.bytes_allocated,0)
        self.assertNotEqual(h,self.call('I915_GEM_CREATE',size=1)['handle'])

    def test_version_nonzero_copy_requires_each_pointer(self):
        for field in ['name','date','desc']:
            with self.subTest(field=field):
                self.error(errno.EFAULT,self.call,'VERSION',**{field:0,field+'_len':8})
                out=self.call('VERSION',**{field:0,field+'_len':0})
                self.assertGreater(out[field+'_len'],0) # size-only query is supported
                pointer=self.arena.allocate(64)
                out=self.call('VERSION',**{field:pointer,field+'_len':64})
                self.assertGreater(out[field+'_len'],0)
                self.assertTrue(any(self.arena.read(pointer,out[field+'_len'])))

    def test_signed_sync_wait_timeout_abi(self):
        raw=self.abi.pack('SYNCOBJ_WAIT',timeout_nsec=-1)
        self.assertEqual(self.abi.unpack('SYNCOBJ_WAIT',raw)['timeout_nsec'],-1)

    def test_invalid_flags_padding_extensions(self):
        self.error(errno.EINVAL,self.call,'I915_GEM_CREATE',size=0)
        self.error(errno.EINVAL,self.call,'I915_GEM_CREATE',size=2**64-1)
        self.error(errno.EINVAL,self.call,'I915_GEM_CREATE',size=4096,pad=1)
        self.error(errno.EINVAL,self.call,'I915_GEM_CONTEXT_CREATE_EXT',extensions=0x1234)
        self.error(errno.EINVAL,self.call,'I915_GEM_CONTEXT_CREATE_EXT',flags=0x80000000)
        self.error(errno.EINVAL,self.call,'SYNCOBJ_CREATE',flags=0x80000000)

    def test_no_gpu_mapping_query_or_submission(self):
        for name in ['I915_GETPARAM','I915_QUERY','I915_GEM_MMAP_OFFSET','I915_GEM_EXECBUFFER2']:
            self.error(errno.ENOTSUP,self.call,name)
        self.error(errno.ENOTTY,self.dev.ioctl,0xffffffff,b'')
        request=self.abi.data['requests']['I915_GEM_CREATE']['value']
        self.error(errno.ENOTTY,self.dev.ioctl,request^0x40000000,self.abi.pack('I915_GEM_CREATE',size=4096))
        self.error(errno.EFAULT,self.dev.ioctl,request,b'\0'*15)
        self.assertFalse(self.dev.bos)

    def test_context_and_vm_are_only_model_ids(self):
        c=self.call('I915_GEM_CONTEXT_CREATE_EXT')['ctx_id']
        v=self.call('I915_GEM_VM_CREATE')['vm_id']
        self.assertFalse(self.dev.vms[v]['gpu_va_available'])
        self.assertEqual(self.dev.contexts[c]['kind'],'CPU_MODEL_ONLY')
        self.call('I915_GEM_CONTEXT_DESTROY',ctx_id=c)
        self.call('I915_GEM_VM_DESTROY',vm_id=v)
        self.error(errno.ENOENT,self.call,'I915_GEM_VM_DESTROY',vm_id=v)

    def test_sync_never_completes_unexecuted_batch(self):
        h=self.call('SYNCOBJ_CREATE')['handle']
        ptr=self.arena.allocate(4,h.to_bytes(4,'little'))
        self.error(errno.ETIME,self.call,'SYNCOBJ_WAIT',handles=ptr,count_handles=1)
        self.error(errno.ENOTSUP,self.call,'I915_GEM_EXECBUFFER2')
        self.error(errno.ETIME,self.call,'SYNCOBJ_WAIT',handles=ptr,count_handles=1)
        self.call('SYNCOBJ_SIGNAL',handles=ptr,count_handles=1) # explicitly CPU model signal
        self.assertEqual(self.call('SYNCOBJ_WAIT',handles=ptr,count_handles=1)['first_signaled'],0)
        self.call('SYNCOBJ_RESET',handles=ptr,count_handles=1)
        self.error(errno.ETIME,self.call,'SYNCOBJ_WAIT',handles=ptr,count_handles=1)
        self.call('SYNCOBJ_DESTROY',handle=h)

    def test_sync_pointer_invalid_atomicity(self):
        h=self.call('SYNCOBJ_CREATE')['handle']
        ptr=self.arena.allocate(8,h.to_bytes(4,'little')+(0xffffffff).to_bytes(4,'little'))
        self.error(errno.ENOENT,self.call,'SYNCOBJ_SIGNAL',handles=ptr,count_handles=2)
        self.assertFalse(self.dev.syncs[h])
        self.error(errno.EINVAL,self.call,'SYNCOBJ_SIGNAL',handles=ptr+1,count_handles=1)
        self.error(errno.EFAULT,self.call,'SYNCOBJ_SIGNAL',handles=ptr+8,count_handles=1)
        self.error(errno.EINVAL,self.call,'SYNCOBJ_SIGNAL',handles=ptr,count_handles=2**32-1)
        self.arena.free(ptr)
        self.error(errno.EFAULT,self.call,'SYNCOBJ_SIGNAL',handles=ptr,count_handles=1)

    def test_capability_and_arena_overflow(self):
        self.assertEqual(self.call('GET_CAP',capability=self.abi.data['constants']['DRM_CAP_PRIME'])['value'],0)
        self.error(errno.EINVAL,self.call,'GET_CAP',capability=0xdead)
        self.error(errno.EFAULT,self.arena.read,2**64-1,4)
        self.error(errno.EINVAL,self.arena.allocate,True)

    def test_close_and_per_session_ownership(self):
        h=self.call('I915_GEM_CREATE',size=4096)['handle']
        other=MockI915(self.abi)
        self.error(errno.ENOENT,other.cpu_bo_read,h,0,1)
        self.dev.close()
        self.assertFalse(self.dev.bos)
        self.error(errno.EBADF,self.call,'I915_GEM_CREATE',size=4096)
        self.error(errno.EBADF,self.dev.cpu_bo_read,h,0,1)

    def test_concurrent_lifecycle(self):
        def run(i):
            out=self.call('I915_GEM_CREATE',size=17); h=out['handle']
            value=i.to_bytes(4,'little')
            self.dev.cpu_bo_write(h,0,value)
            self.assertEqual(self.dev.cpu_bo_read(h,0,4),value)
            self.call('GEM_CLOSE',handle=h)
            return h
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: handles=list(pool.map(run,range(128)))
        self.assertEqual(len(set(handles)),128)
        self.assertFalse(self.dev.bos); self.assertEqual(self.dev.bytes_allocated,0)


if __name__=='__main__': unittest.main(verbosity=2)
