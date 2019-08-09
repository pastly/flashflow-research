extern crate libc;
extern crate serde;
#[macro_use]
extern crate lazy_static;

use libc::c_char;
use serde::{Deserialize, Serialize};
use std::collections::hash_map::RandomState;
use std::collections::{HashMap, HashSet};
use std::ffi::{CStr, CString};
use std::fs::OpenOptions;
use std::io::{BufRead, BufReader};
use std::iter::FromIterator;
use std::mem;
use std::sync::Mutex;

lazy_static! {
    static ref MSMS: Mutex<HashMap<u32, Measurement>> = Mutex::new(HashMap::new());
}

//#[repr(C)]
#[derive(Debug, Serialize, Deserialize)]
pub struct Measurement {
    id: u32,
    fp: String,
    dur: u32,
    state: State,
    hosts: Vec<Host>,
    depends: Vec<u32>,
    finished_depends: Vec<u32>,
}

#[no_mangle]
pub extern "C" fn sched_get_fp(m_id: u32) -> *const c_char {
    CString::new(MSMS.lock().unwrap().get(&m_id).unwrap().fp.clone())
        .expect("Unable to make fp cstring")
        .into_raw()
}

#[no_mangle]
pub extern "C" fn sched_get_dur(m_id: u32) -> u32 {
    MSMS.lock().unwrap().get(&m_id).unwrap().dur
}

//#[repr(C)]
#[derive(Debug, Serialize, Deserialize)]
pub struct Host {
    class: String,
    bw: u32,
    conns: u32,
}

#[derive(PartialEq, Debug, Serialize, Deserialize)]
pub enum State {
    Waiting,
    InProgress,
    Complete,
}

impl Measurement {
    fn new_from_string(s: String) -> Option<Self> {
        let s = s.trim();
        if s.is_empty() || s.starts_with('#') {
            return None;
        }
        let mut word_num = 0;
        let mut id = 0;
        let mut fp = String::new();
        let mut dur = 0;
        let mut host_class = vec![];
        let mut host_bw: Vec<u32> = vec![];
        let mut host_conns: Vec<u32> = vec![];
        let mut depends: Vec<u32> = vec![];
        for sub in s.split(' ') {
            let sub = sub.trim();
            if sub.is_empty() {
                continue;
            }
            match word_num {
                0 => id = sub.parse().unwrap(),
                1 => fp = sub.to_string(),
                2 => dur = sub.parse().unwrap(),
                3 => host_class = sub.split(',').collect(),
                4 => host_bw = sub.split(',').map(|i| i.parse::<u32>().unwrap()).collect(),
                //4 => host_bw = sub.split(',').map(|i| i.parse::<u32>().unwrap() * 1000 * 1000 / 8).collect(),
                5 => host_conns = sub.split(',').map(|i| i.parse().unwrap()).collect(),
                6 => {
                    depends = sub
                        .split(',')
                        .map(|i| i.parse().unwrap())
                        .filter(|i| *i > 0)
                        .collect()
                }
                _ => return None,
            }
            word_num += 1;
        }
        if id == 0 {
            panic!("No measurement can have ID 0");
        }
        if depends.contains(&id) {
            //return None;
            panic!("Measurement cannot depend on itself");
        }
        if host_class.len() != host_bw.len() || host_class.len() != host_conns.len() {
            return None;
        }
        let mut hosts = vec![];
        for i in 0..host_class.len() {
            hosts.push(Host {
                class: host_class[i].to_string(),
                bw: host_bw[i],
                conns: host_conns[i],
            });
        }
        Some(Measurement {
            id,
            fp,
            dur,
            state: State::Waiting,
            hosts,
            depends,
            finished_depends: vec![],
        })
    }
}

#[no_mangle]
pub extern "C" fn sched_new(fname: *const c_char) -> usize {
    let fname = unsafe { CStr::from_ptr(fname).to_str() }
        .expect("Got invalid string from C in sched_new()");
    let file = OpenOptions::new()
        .read(true)
        .open(fname)
        .expect("Could not open file in sched_new()");
    let measurements: Vec<Measurement> = BufReader::new(&file)
        .lines()
        .map(|l| Measurement::new_from_string(l.unwrap()))
        .filter(|m| m.is_some())
        .map(|m| m.unwrap())
        .collect();
    let m_ids: HashSet<u32, RandomState> = HashSet::from_iter(measurements.iter().map(|m| m.id));
    if m_ids.len() != measurements.len() {
        panic!("Every measurement must have unique ID in sched_new()");
    }
    let dep_ids: HashSet<u32, RandomState> =
        HashSet::from_iter(measurements.iter().flat_map(|m| m.depends.iter()).copied());
    for id in &dep_ids {
        if !m_ids.contains(id) {
            panic!("Depend ID not a measurement ID");
        }
    }
    {
        let mut msms = MSMS.lock().unwrap();
        for m in measurements {
            //println!("{:?}", &m);
            //println!("{}", serde_json::to_string(&m).unwrap());
            //let m2: Measurement =
            //    serde_json::from_str(&serde_json::to_string(&m).unwrap()).unwrap();
            //println!("{:?}", m2);
            msms.insert(m.id, m);
        }
    }
    sched_num()
}

#[no_mangle]
pub extern "C" fn sched_finished() -> bool {
    sched_num_incomplete() == 0
}

#[no_mangle]
pub extern "C" fn sched_num() -> usize {
    MSMS.lock().unwrap().len()
}

#[no_mangle]
pub extern "C" fn sched_num_complete() -> usize {
    MSMS.lock()
        .unwrap()
        .values()
        .filter(|m| m.state == State::Complete)
        .count()
}

#[no_mangle]
pub extern "C" fn sched_num_incomplete() -> usize {
    MSMS.lock()
        .unwrap()
        .values()
        .filter(|m| m.state != State::Complete)
        .count()
}

#[no_mangle]
pub extern "C" fn sched_next() -> u32 {
    let mut msms = MSMS.lock().unwrap();
    for m in msms.values_mut() {
        if m.state == State::Waiting && m.depends.len() == m.finished_depends.len() {
            m.state = State::InProgress;
            return m.id;
        }
    }
    0
}

#[no_mangle]
pub extern "C" fn sched_mark_done(m_id: u32) {
    let mut msms = MSMS.lock().unwrap();
    if !msms.contains_key(&m_id) {
        panic!("Told that a measurement ID that doesn't exist is done");
    }
    let the_m = msms.get_mut(&m_id).unwrap();
    assert_eq!(the_m.state, State::InProgress);
    the_m.state = State::Complete;
    for m in msms.values_mut() {
        if m.depends.contains(&m_id) {
            m.finished_depends.push(m_id);
        }
    }
}

#[no_mangle]
pub extern "C" fn sched_get_hosts(
    m_id: u32,
    out_classes: *mut *mut *mut c_char,
    out_bws: *mut *mut u32,
    out_conns: *mut *mut u32,
) -> usize {
    let msms = MSMS.lock().unwrap();
    let m = msms.get(&m_id).unwrap();
    let mut classes = vec![];
    let mut bws = vec![];
    let mut conns = vec![];
    for h in &m.hosts {
        classes.push(
            CString::new(h.class.clone())
                .expect("Unable to make host cstring")
                .into_raw(),
        );
        bws.push(h.bw);
        conns.push(h.conns);
    }
    assert_eq!(classes.len(), m.hosts.len());
    assert_eq!(bws.len(), m.hosts.len());
    assert_eq!(conns.len(), m.hosts.len());
    classes.shrink_to_fit();
    bws.shrink_to_fit();
    conns.shrink_to_fit();
    assert_eq!(classes.len(), classes.capacity());
    assert_eq!(bws.len(), bws.capacity());
    assert_eq!(conns.len(), conns.capacity());
    unsafe {
        *out_classes = classes.as_mut_ptr();
        *out_bws = bws.as_mut_ptr();
        *out_conns = conns.as_mut_ptr();
    }
    mem::forget(classes);
    mem::forget(bws);
    mem::forget(conns);
    m.hosts.len()
}

#[no_mangle]
pub extern "C" fn sched_free_hosts(
    classes: *mut *mut c_char,
    bws: *mut u32,
    conns: *mut u32,
    count: usize,
) {
    unsafe {
        for item in Vec::from_raw_parts(classes, count, count) {
            CString::from_raw(item);
        }
        Vec::from_raw_parts(bws, count, count);
        Vec::from_raw_parts(conns, count, count);
    }
}
